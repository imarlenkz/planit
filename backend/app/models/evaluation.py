"""AI evaluations, evaluations, descriptor items, manual reviews, results, analytics."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import PK, IdMixin, TimestampMixin, utcnow


class AIEvaluation(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_evaluations"
    answer_id: Mapped[int] = mapped_column(PK, ForeignKey("answers.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(80))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    response: Mapped[dict | None] = mapped_column(JSON)
    raw_response: Mapped[str | None] = mapped_column(Text)
    schema_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class Evaluation(IdMixin, TimestampMixin, Base):
    __tablename__ = "evaluations"
    answer_id: Mapped[int] = mapped_column(PK, ForeignKey("answers.id", ondelete="CASCADE"), unique=True)
    question_id: Mapped[int] = mapped_column(PK, ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    submission_id: Mapped[int] = mapped_column(PK, ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    method: Mapped[str] = mapped_column(String(16))  # deterministic | ai | manual
    score: Mapped[float] = mapped_column(Float, default=0)
    max_score: Mapped[float] = mapped_column(Float, default=0)
    ai_suggested_score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0)  # 0..100
    status: Mapped[str] = mapped_column(String(16))  # correct|incorrect|partial|doubtful
    review_status: Mapped[str] = mapped_column(String(16), index=True)  # auto_approved|medium|needs_review|approved|overridden
    reasoning: Mapped[str | None] = mapped_column(Text)
    error_category: Mapped[str | None] = mapped_column(String(32))
    expected_answer: Mapped[str | None] = mapped_column(Text)
    teacher_comment: Mapped[str | None] = mapped_column(Text)

    answer = relationship("Answer", back_populates="evaluation")
    items: Mapped[list["EvaluationItem"]] = relationship(back_populates="evaluation", cascade="all, delete-orphan")
    reviews: Mapped[list["ManualReview"]] = relationship(back_populates="evaluation", cascade="all, delete-orphan")


class EvaluationItem(IdMixin, Base):
    __tablename__ = "evaluation_items"
    evaluation_id: Mapped[int] = mapped_column(PK, ForeignKey("evaluations.id", ondelete="CASCADE"), index=True)
    descriptor_id: Mapped[int | None] = mapped_column(PK, ForeignKey("descriptors.id", ondelete="CASCADE"))
    met: Mapped[bool] = mapped_column(Boolean, default=False)
    points_awarded: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    evaluation: Mapped[Evaluation] = relationship(back_populates="items")
    descriptor = relationship("Descriptor")


class ManualReview(IdMixin, TimestampMixin, Base):
    __tablename__ = "manual_reviews"
    evaluation_id: Mapped[int] = mapped_column(PK, ForeignKey("evaluations.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[int | None] = mapped_column(PK, ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(16))  # accept | override | recheck
    old_score: Mapped[float | None] = mapped_column(Float)
    new_score: Mapped[float | None] = mapped_column(Float)
    comment: Mapped[str | None] = mapped_column(Text)
    evaluation: Mapped[Evaluation] = relationship(back_populates="reviews")


class Result(IdMixin, TimestampMixin, Base):
    __tablename__ = "results"
    submission_id: Mapped[int] = mapped_column(PK, ForeignKey("submissions.id", ondelete="CASCADE"), unique=True)
    student_id: Mapped[int | None] = mapped_column(PK, ForeignKey("students.id", ondelete="CASCADE"), index=True)
    assessment_id: Mapped[int] = mapped_column(PK, ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    total_score: Mapped[float] = mapped_column(Float, default=0)
    max_score: Mapped[float] = mapped_column(Float, default=0)
    percent: Mapped[float] = mapped_column(Float, default=0)
    level: Mapped[str] = mapped_column(String(16), default="low")
    feedback: Mapped[str | None] = mapped_column(Text)
    feedback_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, default=list)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[int | None] = mapped_column(PK, ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Analytics(IdMixin, Base):
    __tablename__ = "analytics"
    assessment_id: Mapped[int] = mapped_column(PK, ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    class_id: Mapped[int | None] = mapped_column(PK, ForeignKey("classes.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
