"""Route each answer to the right evaluator by answer type."""
from app.services.ai.service import AIService
from app.services.evaluation.deterministic import DETERMINISTIC_TYPES, EVALUATORS, evaluate_math_final_answer
from app.services.evaluation.types import EvaluationProposal


def evaluate_answer(question, detected: str, flags: list[str], ai: AIService | None = None) -> EvaluationProposal:
    if "unreadable" in flags or "error" in flags:
        return EvaluationProposal("deterministic", detected or "", "", None, 0.0,
                                  "Жауап оқылмады — қолмен тексеру қажет", flags=["manual_review_required"])
    t = question.answer_type
    if t in DETERMINISTIC_TYPES and not (question.descriptors and t in {"table", "short_text"}):
        return EVALUATORS[t](question, detected or "", flags)
    if t == "math" and not question.descriptors:
        p = evaluate_math_final_answer(question, detected)
        if p:
            return p
    ai = ai or AIService()
    return ai.evaluate(question, detected or "")
