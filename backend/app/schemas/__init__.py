"""Pydantic DTOs (API contract)."""
import datetime as dt
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import ANSWER_TYPES, ASSESSMENT_TYPES


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel):
    items: list[Any]
    total: int
    page: int
    size: int


# auth / users
class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=200)


class UserOut(ORM):
    id: int
    email: str
    full_name: str
    role: str
    school_id: int | None
    locale: str
    is_active: bool


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=2, max_length=255)
    role: Literal["admin", "school_admin", "teacher", "student"]
    school_id: int | None = None
    locale: Literal["kk", "ru", "en"] = "kk"


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: Literal["admin", "school_admin", "teacher", "student"] | None = None
    is_active: bool | None = None
    locale: Literal["kk", "ru", "en"] | None = None
    password: str | None = Field(default=None, min_length=8)


class MeUpdate(BaseModel):
    full_name: str | None = None
    locale: Literal["kk", "ru", "en"] | None = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=200)


# org
class SchoolIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    city: str | None = None
    region: str | None = None


class SchoolOut(ORM):
    id: int
    name: str
    city: str | None
    region: str | None


class SubjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str | None = None


class SubjectOut(ORM):
    id: int
    name: str
    code: str | None
    school_id: int | None


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    grade: int = Field(ge=0, le=12)
    letter: str | None = None
    academic_year: str = "2026-2027"
    homeroom_teacher_id: int | None = None
    school_id: int | None = None


class ClassOut(ORM):
    id: int
    name: str
    grade: int
    letter: str | None
    academic_year: str
    school_id: int
    homeroom_teacher_id: int | None
    student_count: int = 0


class StudentIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    class_id: int | None = None
    gender: Literal["m", "f"] | None = None
    student_code: str | None = None


class StudentOut(ORM):
    id: int
    full_name: str
    class_id: int | None
    gender: str | None
    student_code: str
    is_active: bool
    class_name: str | None = None


class ObjectiveIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    description: str
    subject_id: int | None = None
    grade: int | None = None


class ObjectiveOut(ORM):
    id: int
    code: str
    description: str
    subject_id: int | None
    grade: int | None


# assessments
class DescriptorIn(BaseModel):
    number: int = Field(ge=1)
    text: str = Field(min_length=1)
    points: float = Field(gt=0, le=100)
    keywords: list[str] | None = None


class DescriptorOut(ORM):
    id: int
    number: int
    text: str
    points: float
    keywords: list[str] | None


class QuestionIn(BaseModel):
    number: int = Field(ge=1, le=200)
    text: str = ""
    answer_type: str
    correct_answer: Any = None
    max_score: float = Field(gt=0, le=100)
    criteria: str | None = None
    tolerance: float | None = Field(default=None, ge=0)
    options: dict | list | None = None
    objective_id: int | None = None
    descriptors: list[DescriptorIn] = []

    @field_validator("answer_type")
    @classmethod
    def _type(cls, v: str) -> str:
        if v not in ANSWER_TYPES:
            raise ValueError(f"answer_type must be one of {ANSWER_TYPES}")
        return v

    @field_validator("descriptors")
    @classmethod
    def _desc(cls, v: list[DescriptorIn], info) -> list[DescriptorIn]:
        nums = [d.number for d in v]
        if len(nums) != len(set(nums)):
            raise ValueError("descriptor numbers must be unique")
        return v


class QuestionOut(ORM):
    id: int
    number: int
    text: str
    answer_type: str
    correct_answer: Any
    max_score: float
    criteria: str | None
    tolerance: float | None
    options: Any
    objective_id: int | None
    descriptors: list[DescriptorOut]


class AssessmentIn(BaseModel):
    type: str
    title: str = Field(min_length=2, max_length=255)
    subject_id: int
    class_id: int
    academic_year: str = "2026-2027"
    quarter: int | None = Field(default=None, ge=1, le=4)
    section: str | None = None
    topic: str | None = None
    date: dt.date | None = None
    max_score: float = Field(default=0, ge=0, le=1000)
    settings: dict = {}

    @field_validator("type")
    @classmethod
    def _t(cls, v: str) -> str:
        if v not in ASSESSMENT_TYPES:
            raise ValueError(f"type must be one of {ASSESSMENT_TYPES}")
        return v


class AssessmentUpdate(BaseModel):
    title: str | None = None
    quarter: int | None = None
    section: str | None = None
    topic: str | None = None
    date: dt.date | None = None
    max_score: float | None = None
    status: Literal["draft", "active", "completed"] | None = None
    settings: dict | None = None


class AssessmentOut(ORM):
    id: int
    type: str
    title: str
    subject_id: int
    class_id: int
    teacher_id: int
    academic_year: str
    quarter: int | None
    section: str | None
    topic: str | None
    date: dt.date | None
    max_score: float
    status: str
    settings: dict
    created_at: datetime
    subject_name: str | None = None
    class_name: str | None = None
    teacher_name: str | None = None
    question_count: int = 0
    submission_count: int = 0
    needs_review: int = 0


# review
class OverrideIn(BaseModel):
    score: float = Field(ge=0)
    comment: str | None = Field(default=None, max_length=2000)
    status: Literal["correct", "incorrect", "partial", "doubtful"] | None = None
    descriptor_items: list[dict] | None = None  # [{descriptor_id, met}]


class RecheckIn(BaseModel):
    detected_answer: str | None = None
    provider: str | None = None


class AcceptIn(BaseModel):
    comment: str | None = None


class BatchApproveIn(BaseModel):
    min_confidence: float = Field(default=95, ge=0, le=100)
    include_medium: bool = False


class AssignStudentIn(BaseModel):
    student_id: int


class FeedbackIn(BaseModel):
    feedback: str = Field(max_length=5000)


class GenerateIn(BaseModel):
    prompt: str = Field(min_length=5, max_length=2000)
    subject_id: int | None = None
    class_id: int | None = None
    type: str = "BZhB"
    question_count: int = Field(default=6, ge=1, le=30)
    save: bool = False


class BankItemIn(BaseModel):
    subject_id: int | None = None
    grade: int | None = None
    section: str | None = None
    topic: str | None = None
    objective_id: int | None = None
    text: str = Field(min_length=1)
    answer_type: str
    correct_answer: Any = None
    max_score: float = Field(gt=0, le=100)
    criteria: str | None = None
    tolerance: float | None = None
    options: dict | list | None = None
    descriptors: list[DescriptorIn] = []
    tags: list[str] = []


class SettingsIn(BaseModel):
    values: dict[str, Any]
