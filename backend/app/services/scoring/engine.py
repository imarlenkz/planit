"""ScoringEngine — the single place where scores are computed.

Evaluators (deterministic or AI) only *propose*: detected answer, correctness, descriptor judgments and
confidence. The engine turns proposals into an authoritative score with clamping, partial credit,
confidence aggregation and review routing. It never trusts an AI-provided number blindly.
"""
import math
from dataclasses import dataclass, field

from app.core.config import settings
from app.services.evaluation.types import EvaluationProposal


def round_half(x: float) -> float:
    return math.floor(x * 2 + 1e-9) / 2


@dataclass
class ItemScore:
    descriptor_id: int | None
    number: int
    met: bool
    points_awarded: float
    reason: str
    confidence: float


@dataclass
class ScoreResult:
    score: float
    max_score: float
    status: str  # correct | incorrect | partial | doubtful
    confidence: float  # 0..100
    review_status: str  # auto_approved | medium | needs_review
    reasoning: str
    items: list[ItemScore] = field(default_factory=list)
    error_category: str | None = None


@dataclass
class Thresholds:
    high: float = settings.CONFIDENCE_HIGH
    medium: float = settings.CONFIDENCE_MEDIUM
    auto_approve: bool = settings.AUTO_APPROVE_HIGH_CONFIDENCE


def confidence_band(conf: float, th: Thresholds | None = None) -> str:
    th = th or Thresholds()
    if conf >= th.high:
        return "high"
    if conf >= th.medium:
        return "medium"
    return "low"


class ScoringEngine:
    def __init__(self, thresholds: Thresholds | None = None):
        self.th = thresholds or Thresholds()

    def score(self, question, proposal: EvaluationProposal, ocr_confidence: float,
              answer_flags: list[str] | None = None) -> ScoreResult:
        max_score = float(question.max_score)
        flags = set(answer_flags or []) | set(proposal.flags)
        descriptors = list(question.descriptors or [])
        items: list[ItemScore] = []
        reasoning = proposal.reason
        conf_eval = max(0.0, min(1.0, proposal.confidence))

        if descriptors and proposal.descriptors:
            # partial credit by descriptors: Σ points of met descriptors
            judged = {j.number: j for j in proposal.descriptors}
            total = 0.0
            lines = []
            for d in descriptors:
                j = judged.get(d.number)
                met = bool(j and j.met)
                pts = float(d.points) if met else 0.0
                total += pts
                items.append(ItemScore(d.id, d.number, met, pts, j.reason if j else "Бағаланбады",
                                       j.confidence if j else 0.0))
                lines.append(f"{d.number}-дескриптор: {'орындалды +' + _fmt(pts) if met else 'орындалмады +0'}")
            score = min(total, max_score)
            if proposal.suggested_score is not None and abs(proposal.suggested_score - score) > 1e-9:
                # AI number disagrees with its own descriptor judgments → less trust
                conf_eval *= 0.85
                lines.append(f"(AI ұсынған балл {_fmt(proposal.suggested_score)} дескриптор қосындысымен сәйкес емес)")
            reasoning = "\n".join([proposal.reason, *lines]).strip()
        elif proposal.fraction is not None:
            score = round_half(max_score * max(0.0, min(1.0, proposal.fraction)))
            if proposal.fraction >= 1:
                score = max_score
        elif proposal.is_correct is True:
            score = max_score
        elif proposal.suggested_score is not None:
            score = round_half(max(0.0, min(max_score, proposal.suggested_score)))
        else:
            score = 0.0

        score = max(0.0, min(max_score, score))
        ocr_c = max(0.0, min(1.0, ocr_confidence))
        confidence = round(min(ocr_c, conf_eval) * 100, 1)

        manual = bool(flags & {"manual_review_required", "multiple_marks", "unreadable", "empty", "error",
                               "student_unknown"}) or proposal.is_correct is None and proposal.fraction is None \
            and not proposal.descriptors
        band = confidence_band(confidence, self.th)
        if manual or band == "low":
            review = "needs_review"
        elif band == "high" and self.th.auto_approve:
            review = "auto_approved"
        else:
            review = "medium"

        if review == "needs_review" and (proposal.is_correct is None or confidence < self.th.medium):
            status = "doubtful"
        elif score >= max_score - 1e-9 and max_score > 0:
            status = "correct"
        elif score <= 0:
            status = "incorrect"
        else:
            status = "partial"

        return ScoreResult(score=score, max_score=max_score, status=status, confidence=confidence,
                           review_status=review, reasoning=reasoning, items=items,
                           error_category=None if status == "correct" else proposal.error_category)


def _fmt(x: float) -> str:
    return f"{x:g}"


LEVELS = [(85, "high", 5), (65, "medium", 4), (40, "low", 3), (0, "very_low", 2)]


def percent(total: float, max_score: float) -> float:
    return round(total / max_score * 100, 1) if max_score > 0 else 0.0


def level_for(pct: float) -> tuple[str, int]:
    for threshold, level, mark in LEVELS:
        if pct >= threshold:
            return level, mark
    return "very_low", 2
