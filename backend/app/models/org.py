"""Organisation: schools, users, teachers, classes, students, subjects."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import PK, IdMixin, TimestampMixin

ROLES = ("admin", "school_admin", "teacher", "student")


class School(IdMixin, TimestampMixin, Base):
    __tablename__ = "schools"
    name: Mapped[str] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    # the school's code in iMARLEN ID (id.imarlen.kz); SSO users are matched to a school by it
    idp_code: Mapped[str | None] = mapped_column(String(64), unique=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)
    school_id: Mapped[int | None] = mapped_column(PK, ForeignKey("schools.id", ondelete="SET NULL"), index=True)
    locale: Mapped[str] = mapped_column(String(5), default="kk")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # iMARLEN ID subject; set once the account has signed in through SSO
    idp_sub: Mapped[str | None] = mapped_column(String(64), unique=True)

    school: Mapped[School | None] = relationship()
    teacher: Mapped["Teacher | None"] = relationship(back_populates="user", uselist=False)


class Teacher(IdMixin, TimestampMixin, Base):
    __tablename__ = "teachers"
    user_id: Mapped[int] = mapped_column(PK, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    school_id: Mapped[int | None] = mapped_column(PK, ForeignKey("schools.id", ondelete="SET NULL"), index=True)
    position: Mapped[str | None] = mapped_column(String(120))
    user: Mapped[User] = relationship(back_populates="teacher")


class Subject(IdMixin, TimestampMixin, Base):
    __tablename__ = "subjects"
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str | None] = mapped_column(String(40))
    school_id: Mapped[int | None] = mapped_column(PK, ForeignKey("schools.id", ondelete="CASCADE"), index=True)


class SchoolClass(IdMixin, TimestampMixin, Base):
    __tablename__ = "classes"
    school_id: Mapped[int] = mapped_column(PK, ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(20))
    grade: Mapped[int] = mapped_column(Integer)
    letter: Mapped[str | None] = mapped_column(String(5))
    academic_year: Mapped[str] = mapped_column(String(9), default="2026-2027")
    homeroom_teacher_id: Mapped[int | None] = mapped_column(PK, ForeignKey("teachers.id", ondelete="SET NULL"))

    students: Mapped[list["Student"]] = relationship(back_populates="school_class", order_by="Student.full_name")
    teacher_links: Mapped[list["ClassTeacher"]] = relationship(back_populates="school_class", cascade="all, delete-orphan")


class ClassTeacher(IdMixin, Base):
    __tablename__ = "class_teachers"
    __table_args__ = (UniqueConstraint("class_id", "teacher_id", "subject_id"),)
    class_id: Mapped[int] = mapped_column(PK, ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    teacher_id: Mapped[int] = mapped_column(PK, ForeignKey("teachers.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int | None] = mapped_column(PK, ForeignKey("subjects.id", ondelete="CASCADE"))
    school_class: Mapped[SchoolClass] = relationship(back_populates="teacher_links")


class Student(IdMixin, TimestampMixin, Base):
    __tablename__ = "students"
    school_id: Mapped[int] = mapped_column(PK, ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    class_id: Mapped[int | None] = mapped_column(PK, ForeignKey("classes.id", ondelete="SET NULL"), index=True)
    user_id: Mapped[int | None] = mapped_column(PK, ForeignKey("users.id", ondelete="SET NULL"), unique=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    gender: Mapped[str | None] = mapped_column(String(1))
    student_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    school_class: Mapped[SchoolClass | None] = relationship(back_populates="students")
