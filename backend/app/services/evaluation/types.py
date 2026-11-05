from dataclasses import dataclass, field


@dataclass
class DescriptorJudgment:
    descriptor_id: int | None
    number: int
    met: bool
    confidence: float  # 0..1
    reason: str = ""


@dataclass
class EvaluationProposal:
    """What an evaluator (deterministic or AI) proposes. The ScoringEngine decides the final score."""
    method: str  # deterministic | ai
    detected_answer: str
    expected_answer: str
    is_correct: bool | None
    confidence: float  # 0..1 evaluation confidence
    reason: str
    suggested_score: float | None = None
    fraction: float | None = None  # deterministic partial-credit fraction 0..1
    descriptors: list[DescriptorJudgment] = field(default_factory=list)
    error_category: str | None = None
    flags: list[str] = field(default_factory=list)
    ai_record: dict | None = None  # raw provider data for ai_evaluations
