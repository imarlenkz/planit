"""Assessments, versions, questions, descriptors, learning objectives, question bank."""
import datetime as dt

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import PK, IdMixin, TimestampMixin

ASSESSMENT_TYPES = ("BZhB", "TZhB", "AB")  # БЖБ, ТЖБ, АБ
ANSWER_TYPES = (
    "single_choice", "multiple_choice", "numeric", "short_text", "open", "essay", "math",
    "formula", "matching", "table", "graph", "drawing", "handwritten",
)


class LearningObjective(IdMixin, TimestampMixin, Base):
    __tablename__ = "learning_objectives"
    code: Mapped[str] = mapped_column(String(32), index=True)
    description: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[int | None] = mapped_column(PK, ForeignKey("subjects.id", ondelete="SET NULL"))
    grade: Mapped[int | None] = mapped_column(Integer)


class Assessment(IdMixin, TimestampMixin, Base):
    __tablename__ = "assessments"
    type: Mapped[str] = mapped_column(String(8), index=True)
    title: Mapped[str] = mapped_column(String(255))
    subject_id: Mapped[int] = mapped_column(PK, ForeignKey("subjects.id"), index=True)
    class_id: Mapped[int] = mapped_column(PK, ForeignKey("classes.id"), index=True)
    teacher_id: Mapped[int] = mapped_column(PK, ForeignKey("teachers.id"), index=True)
    school_id: Mapped[int] = mapped_column(PK, ForeignKey("schools.id"), index=True)
    academic_year: Mapped[str] = mapped_column(String(9), default="2026-2027")
    quarter: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(255))
    topic: Mapped[str | None] = mapped_column(String(255))
    date: Mapped[dt.date | None] = mapped_column(Date)
    max_score: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    versions: Mapped[list["AssessmentVersion"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan", order_by="AssessmentVersion.id")
    subject = relationship("Subject")
    school_class = relationship("SchoolClass")
    teacher = relationship("Teacher")


class AssessmentVersion(IdMixin, TimestampMixin, Base):
    __tablename__ = "assessment_versions"
    assessment_id: Mapped[int] = mapped_column(PK, ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    version_label: Mapped[str] = mapped_column(String(40), default="1-нұсқа")
    template_layout: Mapped[dict] = mapped_column(JSON, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)

    assessment: Mapped[Assessment] = relationship(back_populates="versions")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="version", cascade="all, delete-orphan", order_by="Question.number")


class Question(IdMixin, TimestampMixin, Base):
    __tablename__ = "questions"
    version_id: Mapped[int] = mapped_column(PK, ForeignKey("assessment_versions.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    answer_type: Mapped[str] = mapped_column(String(24))
    correct_answer: Mapped[dict | list | str | None] = mapped_column(JSON)
    max_score: Mapped[float] = mapped_column(Float, default=1)
    criteria: Mapped[str | None] = mapped_column(Text)
    tolerance: Mapped[float | None] = mapped_column(Float)
    options: Mapped[dict | list | None] = mapped_column(JSON)
    page_hint: Mapped[int | None] = mapped_column(Integer)
    objective_id: Mapped[int | None] = mapped_column(PK, ForeignKey("learning_objectives.id", ondelete="SET NULL"))

    version: Mapped[AssessmentVersion] = relationship(back_populates="questions")
    descriptors: Mapped[list["Descriptor"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="Descriptor.number")
    objective: Mapped[LearningObjective | None] = relationship()


class Descriptor(IdMixin, TimestampMixin, Base):
    __tablename__ = "descriptors"
    question_id: Mapped[int] = mapped_column(PK, ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    points: Mapped[float] = mapped_column(Float, default=1)
    keywords: Mapped[list | None] = mapped_column(JSON)

    question: Mapped[Question] = relationship(back_populates="descriptors")


class QuestionBankItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "question_bank_items"
    owner_id: Mapped[int] = mapped_column(PK, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int | None] = mapped_column(PK, ForeignKey("subjects.id", ondelete="SET NULL"))
    grade: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(255))
    topic: Mapped[str | None] = mapped_column(String(255))
    objective_id: Mapped[int | None] = mapped_column(PK, ForeignKey("learning_objectives.id", ondelete="SET NULL"))
    text: Mapped[str] = mapped_column(Text)
    answer_type: Mapped[str] = mapped_column(String(24))
    correct_answer: Mapped[dict | list | str | None] = mapped_column(JSON)
    max_score: Mapped[float] = mapped_column(Float, default=1)
    criteria: Mapped[str | None] = mapped_column(Text)
    tolerance: Mapped[float | None] = mapped_column(Float)
    options: Mapped[dict | list | None] = mapped_column(JSON)
    descriptors: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)
