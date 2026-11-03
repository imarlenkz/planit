"""FastAPI dependencies: authentication, CSRF, RBAC and tenant scoping."""
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_token
from app.models import Assessment, ClassTeacher, SchoolClass, Student, Teacher, User

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = None
    via_cookie = False
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:]
    elif request.cookies.get("access_token"):
        token = request.cookies["access_token"]
        via_cookie = True
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Кіру қажет")
    payload = decode_token(token, "access")
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сессия мерзімі өтті")
    # CSRF: double-submit cookie for cookie-authenticated state-changing requests
    if via_cookie and request.method not in SAFE_METHODS:
        header = request.headers.get("X-CSRF-Token")
        if not header or header != request.cookies.get("csrf_token"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF токен жарамсыз")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Пайдаланушы табылмады")
    return user


def require_roles(*roles: str) -> Callable[[User], User]:
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Рұқсат жоқ")
        return user

    return dep


staff = require_roles("admin", "school_admin", "teacher")
teacher_or_admin = staff
admins = require_roles("admin", "school_admin")
superadmin = require_roles("admin")


def teacher_of(db: Session, user: User) -> Teacher | None:
    return db.scalar(select(Teacher).where(Teacher.user_id == user.id))


def accessible_class_ids(db: Session, user: User) -> list[int] | None:
    """None = unrestricted (global admin)."""
    if user.role == "admin":
        return None
    if user.role == "school_admin":
        return list(db.scalars(select(SchoolClass.id).where(SchoolClass.school_id == user.school_id)))
    if user.role == "teacher":
        t = teacher_of(db, user)
        if not t:
            return []
        ids = set(db.scalars(select(ClassTeacher.class_id).where(ClassTeacher.teacher_id == t.id)))
        ids |= set(db.scalars(select(SchoolClass.id).where(SchoolClass.homeroom_teacher_id == t.id)))
        return sorted(ids)
    if user.role == "student":
        s = db.scalar(select(Student).where(Student.user_id == user.id))
        return [s.class_id] if s and s.class_id else []
    return []


def assessment_query_filter(db: Session, user: User):
    """SQL filter restricting assessments to what the user may see."""
    if user.role == "admin":
        return True
    if user.role == "school_admin":
        return Assessment.school_id == user.school_id
    if user.role == "teacher":
        t = teacher_of(db, user)
        tid = t.id if t else -1
        return or_(Assessment.teacher_id == tid, Assessment.class_id.in_(accessible_class_ids(db, user) or [-1]))
    if user.role == "student":
        return Assessment.class_id.in_(accessible_class_ids(db, user) or [-1])
    return False


def get_assessment_or_404(db: Session, user: User, assessment_id: int, write: bool = False) -> Assessment:
    a = db.get(Assessment, assessment_id)
    if not a:
        raise HTTPException(404, "Бағалау табылмады")
    ok = False
    if user.role == "admin":
        ok = True
    elif user.role == "school_admin":
        ok = a.school_id == user.school_id
    elif user.role == "teacher":
        t = teacher_of(db, user)
        ok = bool(t) and (a.teacher_id == t.id or (not write and a.class_id in (accessible_class_ids(db, user) or [])))
    elif user.role == "student" and not write:
        ok = a.class_id in (accessible_class_ids(db, user) or [])
    if not ok:
        raise HTTPException(404, "Бағалау табылмады")
    return a


def check_student_access(db: Session, user: User, student: Student) -> None:
    if user.role == "admin":
        return
    if user.role == "school_admin" and student.school_id == user.school_id:
        return
    if user.role == "teacher" and student.class_id in (accessible_class_ids(db, user) or []):
        return
    if user.role == "student" and student.user_id == user.id:
        return
    raise HTTPException(404, "Оқушы табылмады")


def check_class_access(db: Session, user: User, class_id: int) -> SchoolClass:
    c = db.get(SchoolClass, class_id)
    allowed = accessible_class_ids(db, user)
    if not c or (allowed is not None and class_id not in allowed):
        raise HTTPException(404, "Сынып табылмады")
    return c
