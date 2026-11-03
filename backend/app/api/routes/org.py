"""Users, schools, subjects, classes, students, learning objectives."""
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import (
    accessible_class_ids,
    admins,
    check_class_access,
    check_student_access,
    get_current_user,
    staff,
    superadmin,
    teacher_of,
)
from app.core.pagination import PageParams
from app.core.security import hash_password
from app.models import (
    Answer,
    ClassTeacher,
    LearningObjective,
    Result,
    School,
    SchoolClass,
    Student,
    Subject,
    Submission,
    Teacher,
    User,
)
from app.schemas import (
    ClassIn,
    ClassOut,
    ObjectiveIn,
    ObjectiveOut,
    SchoolIn,
    SchoolOut,
    StudentIn,
    StudentOut,
    SubjectIn,
    SubjectOut,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.services.audit import audit

router = APIRouter(tags=["organisation"])


# ---------- users ----------
@router.get("/users")
def list_users(q: str | None = None, role: str | None = None, p: PageParams = Depends(), db: Session = Depends(get_db),
               user: User = Depends(admins)):
    stmt = select(User)
    if user.role == "school_admin":
        stmt = stmt.where(User.school_id == user.school_id)
    if role:
        stmt = stmt.where(User.role == role)
    if q:
        stmt = stmt.where(or_(User.full_name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(User.full_name).offset(p.offset).limit(p.size))
    return {"items": [UserOut.model_validate(u) for u in items], "total": total, "page": p.page, "size": p.size}


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(admins)):
    if user.role == "school_admin":
        if body.role == "admin":
            raise HTTPException(403, "Рұқсат жоқ")
        body.school_id = user.school_id
    if db.scalar(select(User).where(func.lower(User.email) == body.email.lower())):
        raise HTTPException(409, "Бұл email тіркелген")
    u = User(email=body.email.lower(), password_hash=hash_password(body.password), full_name=body.full_name,
             role=body.role, school_id=body.school_id, locale=body.locale)
    db.add(u)
    db.flush()
    if u.role == "teacher":
        db.add(Teacher(user_id=u.id, school_id=u.school_id))
    audit(db, user, "user.create", "user", u.id, after={"email": u.email, "role": u.role}, request=request)
    db.commit()
    return u


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, request: Request, db: Session = Depends(get_db),
                user: User = Depends(admins)):
    u = db.get(User, user_id)
    if not u or (user.role == "school_admin" and u.school_id != user.school_id):
        raise HTTPException(404, "Пайдаланушы табылмады")
    data = body.model_dump(exclude_none=True)
    if user.role == "school_admin" and data.get("role") == "admin":
        raise HTTPException(403, "Рұқсат жоқ")
    before = {"role": u.role, "is_active": u.is_active}
    if "password" in data:
        u.password_hash = hash_password(data.pop("password"))
    for k, v in data.items():
        setattr(u, k, v)
    if u.role == "teacher" and not db.scalar(select(Teacher).where(Teacher.user_id == u.id)):
        db.add(Teacher(user_id=u.id, school_id=u.school_id))
    audit(db, user, "user.update", "user", u.id, before=before, after={"role": u.role, "is_active": u.is_active},
          request=request)
    db.commit()
    return u


@router.get("/teachers")
def list_teachers(db: Session = Depends(get_db), user: User = Depends(staff)):
    stmt = select(Teacher, User).join(User, User.id == Teacher.user_id)
    if user.role != "admin":
        stmt = stmt.where(Teacher.school_id == user.school_id)
    return [{"id": t.id, "user_id": u.id, "full_name": u.full_name, "email": u.email} for t, u in db.execute(stmt)]


# ---------- schools ----------
@router.get("/schools", response_model=list[SchoolOut])
def list_schools(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == "admin":
        return list(db.scalars(select(School).order_by(School.name)))
    return [user.school] if user.school else []


@router.post("/schools", response_model=SchoolOut, status_code=201)
def create_school(body: SchoolIn, request: Request, db: Session = Depends(get_db), user: User = Depends(superadmin)):
    s = School(**body.model_dump())
    db.add(s)
    db.flush()
    audit(db, user, "school.create", "school", s.id, after=body.model_dump(), request=request)
    db.commit()
    return s


@router.patch("/schools/{school_id}", response_model=SchoolOut)
def update_school(school_id: int, body: SchoolIn, db: Session = Depends(get_db), user: User = Depends(admins)):
    s = db.get(School, school_id)
    if not s or (user.role != "admin" and s.id != user.school_id):
        raise HTTPException(404, "Мектеп табылмады")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    db.commit()
    return s


# ---------- subjects ----------
@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Subject).order_by(Subject.name)
    if user.role != "admin":
        stmt = stmt.where(or_(Subject.school_id.is_(None), Subject.school_id == user.school_id))
    return list(db.scalars(stmt))


@router.post("/subjects", response_model=SubjectOut, status_code=201)
def create_subject(body: SubjectIn, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    s = Subject(name=body.name, code=body.code, school_id=user.school_id)
    db.add(s)
    db.flush()
    audit(db, user, "subject.create", "subject", s.id, after=body.model_dump(), request=request)
    db.commit()
    return s


@router.delete("/subjects/{subject_id}", status_code=204)
def delete_subject(subject_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(admins)):
    s = db.get(Subject, subject_id)
    if not s or (user.role != "admin" and s.school_id != user.school_id):
        raise HTTPException(404, "Пән табылмады")
    db.delete(s)
    audit(db, user, "subject.delete", "subject", subject_id, request=request)
    db.commit()


# ---------- classes ----------
def _class_out(db: Session, c: SchoolClass) -> ClassOut:
    out = ClassOut.model_validate(c)
    out.student_count = db.scalar(select(func.count()).where(Student.class_id == c.id, Student.is_active.is_(True))) or 0
    return out


@router.get("/classes", response_model=list[ClassOut])
def list_classes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ids = accessible_class_ids(db, user)
    stmt = select(SchoolClass).order_by(SchoolClass.grade, SchoolClass.name)
    if ids is not None:
        stmt = stmt.where(SchoolClass.id.in_(ids or [-1]))
    return [_class_out(db, c) for c in db.scalars(stmt)]


@router.post("/classes", response_model=ClassOut, status_code=201)
def create_class(body: ClassIn, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    school_id = body.school_id if user.role == "admin" and body.school_id else user.school_id
    if not school_id:
        raise HTTPException(400, "Мектеп көрсетілмеген")
    c = SchoolClass(school_id=school_id, **body.model_dump(exclude={"school_id"}))
    db.add(c)
    db.flush()
    if user.role == "teacher":  # a teacher creating a class becomes its teacher
        t = teacher_of(db, user)
        if t:
            db.add(ClassTeacher(class_id=c.id, teacher_id=t.id))
            c.homeroom_teacher_id = c.homeroom_teacher_id or t.id
    audit(db, user, "class.create", "class", c.id, after={"name": c.name}, request=request)
    db.commit()
    return _class_out(db, c)


@router.patch("/classes/{class_id}", response_model=ClassOut)
def update_class(class_id: int, body: ClassIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    c = check_class_access(db, user, class_id)
    for k, v in body.model_dump(exclude={"school_id"}).items():
        setattr(c, k, v)
    db.commit()
    return _class_out(db, c)


@router.delete("/classes/{class_id}", status_code=204)
def delete_class(class_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(admins)):
    c = check_class_access(db, user, class_id)
    db.delete(c)
    audit(db, user, "class.delete", "class", class_id, request=request)
    db.commit()


@router.post("/classes/{class_id}/teachers")
def assign_teacher(class_id: int, teacher_id: int, subject_id: int | None = None, db: Session = Depends(get_db),
                   user: User = Depends(admins)):
    check_class_access(db, user, class_id)
    db.add(ClassTeacher(class_id=class_id, teacher_id=teacher_id, subject_id=subject_id))
    db.commit()
    return {"ok": True}


# ---------- students ----------
def _student_out(s: Student) -> StudentOut:
    o = StudentOut.model_validate(s)
    o.class_name = s.school_class.name if s.school_class else None
    return o


@router.get("/students")
def list_students(class_id: int | None = None, q: str | None = None, p: PageParams = Depends(),
                  db: Session = Depends(get_db), user: User = Depends(staff)):
    ids = accessible_class_ids(db, user)
    stmt = select(Student).where(Student.is_active.is_(True))
    if ids is not None:
        stmt = stmt.where(Student.class_id.in_(ids or [-1]))
    if class_id:
        stmt = stmt.where(Student.class_id == class_id)
    if q:
        stmt = stmt.where(Student.full_name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(Student.full_name).offset(p.offset).limit(p.size))
    return {"items": [_student_out(s) for s in items], "total": total, "page": p.page, "size": p.size}


@router.post("/students", response_model=StudentOut, status_code=201)
def create_student(body: StudentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    if body.class_id:
        c = check_class_access(db, user, body.class_id)
        school_id = c.school_id
    else:
        school_id = user.school_id
    s = Student(full_name=body.full_name.strip(), class_id=body.class_id, gender=body.gender, school_id=school_id,
                student_code=body.student_code or f"S{secrets.token_hex(4).upper()}")
    db.add(s)
    db.flush()
    audit(db, user, "student.create", "student", s.id, after={"full_name": s.full_name}, request=request)
    db.commit()
    return _student_out(s)


@router.post("/students/bulk", status_code=201)
def bulk_students(class_id: int, names: list[str], request: Request, db: Session = Depends(get_db),
                  user: User = Depends(staff)):
    """Paste a roster: one name per line (optionally 'Аты Тегі;m')."""
    c = check_class_access(db, user, class_id)
    created = 0
    for line in names:
        name, _, g = line.partition(";")
        if len(name.strip()) < 2:
            continue
        db.add(Student(full_name=name.strip(), class_id=class_id, school_id=c.school_id,
                       gender=g.strip() if g.strip() in ("m", "f") else None,
                       student_code=f"S{secrets.token_hex(4).upper()}"))
        created += 1
    audit(db, user, "student.bulk_create", "class", class_id, after={"count": created}, request=request)
    db.commit()
    return {"created": created}


@router.get("/students/{student_id}", response_model=StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.get(Student, student_id)
    if not s:
        raise HTTPException(404, "Оқушы табылмады")
    check_student_access(db, user, s)
    return _student_out(s)


@router.patch("/students/{student_id}", response_model=StudentOut)
def update_student(student_id: int, body: StudentIn, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(staff)):
    s = db.get(Student, student_id)
    if not s:
        raise HTTPException(404, "Оқушы табылмады")
    check_student_access(db, user, s)
    if body.class_id and body.class_id != s.class_id:
        check_class_access(db, user, body.class_id)
    before = {"full_name": s.full_name, "class_id": s.class_id}
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    audit(db, user, "student.update", "student", s.id, before=before, after=body.model_dump(), request=request)
    db.commit()
    return _student_out(s)


@router.delete("/students/{student_id}", status_code=204)
def delete_student(student_id: int, request: Request, purge: bool = Query(False), db: Session = Depends(get_db),
                   user: User = Depends(staff)):
    """Soft-delete by default; purge=true removes the student and all their works/results (right to erasure)."""
    s = db.get(Student, student_id)
    if not s:
        raise HTTPException(404, "Оқушы табылмады")
    check_student_access(db, user, s)
    if purge:
        for sub in db.scalars(select(Submission).where(Submission.student_id == s.id)):
            db.delete(sub)
        db.delete(s)
    else:
        s.is_active = False
    audit(db, user, "student.purge" if purge else "student.deactivate", "student", student_id, request=request)
    db.commit()


@router.get("/students/{student_id}/export")
def export_student_data(student_id: int, request: Request, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """Privacy: machine-readable export of everything stored about a student."""
    s = db.get(Student, student_id)
    if not s:
        raise HTTPException(404, "Оқушы табылмады")
    check_student_access(db, user, s)
    subs = list(db.scalars(select(Submission).where(Submission.student_id == s.id)))
    data = {"student": _student_out(s).model_dump(), "submissions": []}
    for sub in subs:
        res = db.scalar(select(Result).where(Result.submission_id == sub.id))
        answers = list(db.scalars(select(Answer).where(Answer.submission_id == sub.id)))
        data["submissions"].append({
            "assessment_id": sub.assessment_id, "status": sub.status, "created_at": sub.created_at.isoformat(),
            "result": {"total": res.total_score, "max": res.max_score, "percent": res.percent, "feedback": res.feedback}
            if res else None,
            "answers": [{"question_id": a.question_id, "detected_answer": a.detected_answer,
                         "score": a.evaluation.score if a.evaluation else None} for a in answers]})
    audit(db, user, "student.export", "student", s.id, request=request, commit=True)
    return Response(json.dumps(data, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="student-{s.id}.json"'})


# ---------- learning objectives ----------
@router.get("/objectives", response_model=list[ObjectiveOut])
def list_objectives(subject_id: int | None = None, grade: int | None = None, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    stmt = select(LearningObjective).order_by(LearningObjective.code)
    if subject_id:
        stmt = stmt.where(LearningObjective.subject_id == subject_id)
    if grade:
        stmt = stmt.where(LearningObjective.grade == grade)
    return list(db.scalars(stmt))


@router.post("/objectives", response_model=ObjectiveOut, status_code=201)
def create_objective(body: ObjectiveIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    o = LearningObjective(**body.model_dump())
    db.add(o)
    db.commit()
    return o


@router.patch("/objectives/{oid}", response_model=ObjectiveOut)
def update_objective(oid: int, body: ObjectiveIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    o = db.get(LearningObjective, oid)
    if not o:
        raise HTTPException(404, "Табылмады")
    for k, v in body.model_dump().items():
        setattr(o, k, v)
    db.commit()
    return o


@router.delete("/objectives/{oid}", status_code=204)
def delete_objective(oid: int, db: Session = Depends(get_db), user: User = Depends(admins)):
    o = db.get(LearningObjective, oid)
    if o:
        db.delete(o)
        db.commit()
