"""Files, processing jobs, submissions, pages, OCR results, answers."""
from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import PK, IdMixin, TimestampMixin


class File(IdMixin, TimestampMixin, Base):
    __tablename__ = "files"
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    original_name: Mapped[str | None] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    kind: Mapped[str] = mapped_column(String(16), default="upload")
    uploaded_by: Mapped[int | None] = mapped_column(PK, ForeignKey("users.id", ondelete="SET NULL"))
    school_id: Mapped[int | None] = mapped_column(PK, ForeignKey("schools.id", ondelete="CASCADE"), index=True)


class ProcessingJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "processing_jobs"
    assessment_id: Mapped[int] = mapped_column(PK, ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[int | None] = mapped_column(PK, ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|done|failed
    stage: Mapped[str] = mapped_column(String(24), default="uploading")
    progress: Mapped[float] = mapped_column(Float, default=0)
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    processed_pages: Mapped[int] = mapped_column(Integer, default=0)
    file_ids: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)


class Submission(IdMixin, TimestampMixin, Base):
    __tablename__ = "submissions"
    assessment_id: Mapped[int] = mapped_column(PK, ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[int | None] = mapped_column(PK, ForeignKey("assessment_versions.id", ondelete="SET NULL"))
    student_id: Mapped[int | None] = mapped_column(PK, ForeignKey("students.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[int | None] = mapped_column(PK, ForeignKey("processing_jobs.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="processing")
    detection_method: Mapped[str | None] = mapped_column(String(16))
    detection_confidence: Mapped[float | None] = mapped_column(Float)
    detected_name: Mapped[str | None] = mapped_column(String(255))
    flags: Mapped[list] = mapped_column(JSON, default=list)

    pages: Mapped[list["SubmissionPage"]] = relationship(
        back_populates="submission", order_by="SubmissionPage.page_number", cascade="all, delete-orphan")
    answers: Mapped[list["Answer"]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    student = relationship("Student")
    assessment = relationship("Assessment")


class SubmissionPage(IdMixin, TimestampMixin, Base):
    __tablename__ = "submission_pages"
    submission_id: Mapped[int | None] = mapped_column(PK, ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[int | None] = mapped_column(PK, ForeignKey("processing_jobs.id", ondelete="SET NULL"), index=True)
    file_id: Mapped[int | None] = mapped_column(PK, ForeignKey("files.id", ondelete="SET NULL"))
    original_file_id: Mapped[int | None] = mapped_column(PK, ForeignKey("files.id", ondelete="SET NULL"))
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    source_page_index: Mapped[int] = mapped_column(Integer, default=0)
    qr_payload: Mapped[dict | None] = mapped_column(JSON)
    quality_score: Mapped[float | None] = mapped_column(Float)
    preprocessing: Mapped[dict] = mapped_column(JSON, default=dict)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="ok")

    submission: Mapped[Submission | None] = relationship(back_populates="pages")
    ocr: Mapped["OCRResult | None"] = relationship(back_populates="page", uselist=False, cascade="all, delete-orphan")


class OCRResult(IdMixin, TimestampMixin, Base):
    __tablename__ = "ocr_results"
    page_id: Mapped[int] = mapped_column(PK, ForeignKey("submission_pages.id", ondelete="CASCADE"), unique=True)
    provider: Mapped[str] = mapped_column(String(40))
    language: Mapped[str] = mapped_column(String(40))
    full_text: Mapped[str] = mapped_column(Text, default="")
    words: Mapped[list] = mapped_column(JSON, default=list)
    mean_confidence: Mapped[float] = mapped_column(Float, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    page: Mapped[SubmissionPage] = relationship(back_populates="ocr")


class Answer(IdMixin, TimestampMixin, Base):
    __tablename__ = "answers"
    submission_id: Mapped[int] = mapped_column(PK, ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(PK, ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    page_id: Mapped[int | None] = mapped_column(PK, ForeignKey("submission_pages.id", ondelete="SET NULL"))
    bbox: Mapped[dict | None] = mapped_column(JSON)  # normalised {x,y,w,h} 0..1
    detected_answer: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0)
    flags: Mapped[list] = mapped_column(JSON, default=list)

    submission: Mapped[Submission] = relationship(back_populates="answers")
    question = relationship("Question")
    evaluation: Mapped["Evaluation | None"]  # noqa: F821 = relationship(back_populates="answer", uselist=False, cascade="all, delete-orphan")
