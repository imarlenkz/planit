"""AIService: picks a provider, validates output, never lets the AI decide the final score."""
import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutTimeout

from app.core.config import settings
from app.services.ai.base import EvalRequest, LLMProvider
from app.services.ai.local import LocalProvider
from app.services.ai.schema import SchemaError, validate_evaluation
from app.services.evaluation.types import DescriptorJudgment, EvaluationProposal

log = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=8)


def get_provider(name: str | None = None) -> LLMProvider:
    name = (name or settings.AI_PROVIDER).lower()
    if name == "openai":
        from app.services.ai.remote import OpenAIProvider
        return OpenAIProvider()
    if name == "anthropic":
        from app.services.ai.remote import AnthropicProvider
        return AnthropicProvider()
    return LocalProvider()


class AIService:
    def __init__(self, provider: LLMProvider | None = None):
        try:
            self.provider = provider or get_provider()
        except Exception as e:  # missing key etc. → local, but record it
            log.warning("AI provider unavailable (%s); falling back to local", e)
            self.provider = LocalProvider()

    def evaluate(self, question, student_answer: str) -> EvaluationProposal:
        descs = [{"number": d.number, "text": d.text, "points": d.points, "keywords": d.keywords or [],
                  "id": d.id} for d in question.descriptors]
        ca = question.correct_answer
        ref = ca.get("value") if isinstance(ca, dict) and "value" in ca else ca
        req = EvalRequest(question_text=question.text or "", answer_type=question.answer_type,
                          reference_answer=ref if isinstance(ref, str) else json.dumps(ref, ensure_ascii=False),
                          criteria=question.criteria or "", max_score=float(question.max_score),
                          descriptors=[{k: v for k, v in d.items() if k != "id"} for d in descs],
                          student_answer=student_answer or "")
        req_hash = hashlib.sha256(json.dumps(req.__dict__, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        record = {"provider": self.provider.name, "model": getattr(self.provider, "model", None),
                  "request_hash": req_hash}
        t0 = time.monotonic()
        if not settings.AI_ENABLED:
            return self._manual(req, record, "AI өшірілген (баптау)")
        try:
            fut = _pool.submit(self.provider.evaluate, req)
            data, raw = fut.result(timeout=settings.AI_TIMEOUT_SEC)
            record["raw_response"] = raw[:20000]
            record["latency_ms"] = int((time.monotonic() - t0) * 1000)
            data = validate_evaluation(data, float(question.max_score), {d["number"] for d in descs})
        except FutTimeout:
            record["latency_ms"] = int((time.monotonic() - t0) * 1000)
            return self._manual(req, record, "AI timeout")
        except SchemaError as e:
            record["error"] = str(e)
            return self._manual(req, record, f"AI жауабы схемаға сай емес: {e}")
        except Exception as e:
            record["error"] = repr(e)[:500]
            return self._manual(req, record, "AI API қатесі")
        record.update(response=data, schema_valid=True)
        by_num = {d["number"]: d for d in descs}
        judgments = [DescriptorJudgment(by_num[j["number"]]["id"], j["number"], bool(j["met"]),
                                        float(data["confidence"]), j["reason"]) for j in data["descriptors"]]
        return EvaluationProposal(method="ai", detected_answer=student_answer, expected_answer=req.reference_answer,
                                  is_correct=data["is_correct"], confidence=float(data["confidence"]),
                                  reason=data["reason"], suggested_score=float(data["score"]),
                                  descriptors=judgments, error_category=data.get("error_category"),
                                  ai_record=record)

    @staticmethod
    def _manual(req: EvalRequest, record: dict, why: str) -> EvaluationProposal:
        record.setdefault("error", why)
        record["schema_valid"] = False
        return EvaluationProposal(method="ai", detected_answer=req.student_answer, expected_answer=req.reference_answer,
                                  is_correct=None, confidence=0.0, reason=why, suggested_score=None,
                                  flags=["manual_review_required"], ai_record=record)

    def complete_json(self, system: str, prompt: str, schema: dict) -> dict:
        return self.provider.complete_json(system, prompt, schema)
