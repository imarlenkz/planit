"""Assessments, answer keys (questions + descriptors), scan templates."""
import io
import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.deps import (
    assessment_query_filter,
    check_class_access,
    get_assessment_or_404,
    get_current_user,
    staff,
    teacher_of,
)
from app.core.pagination import PageParams
from app.models import (
    ANSWER_TYPES,
    Assessment,
    AssessmentVersion,
    Descriptor,
    Evaluation,
    Question,
    School,
    SchoolClass,
    Student,
    Subject,
    Submission,
    Teacher,
    User,
)
from app.schemas import AssessmentIn, AssessmentOut, AssessmentUpdate, QuestionIn, QuestionOut
from app.services.audit import audit
from app.services.templates import build_layout, render_template_pdf

router = APIRouter(prefix="/assessments", tags=["assessments"])


def _out(db: Session, a: Assessment) -> AssessmentOut:
    o = AssessmentOut.model_validate(a)
    o.subject_name = a.subject.name if a.subject else None
    o.class_name = a.school_class.name if a.school_class else None
    o.teacher_name = a.teacher.user.full_name if a.teacher and a.teacher.user else None
    vid = default_version(a).id if a.versions else -1
    o.question_count = db.scalar(select(func.count()).where(Question.version_id == vid)) or 0
    o.submission_count = db.scalar(select(func.count()).where(Submission.assessment_id == a.id)) or 0
    o.needs_review = db.scalar(select(func.count()).select_from(Evaluation).join(Submission, Submission.id == Evaluation.submission_id)
                               .where(Submission.assessment_id == a.id, Evaluation.review_status == "needs_review")) or 0
    return o


def default_version(a: Assessment) -> AssessmentVersion:
    return next((v for v in a.versions if v.is_default), a.versions[0])


@router.get("")
def list_assessments(type: str | None = None, class_id: int | None = None, subject_id: int | None = None,
                     status: str | None = None, q: str | None = None, p: PageParams = Depends(),
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Assessment).where(assessment_query_filter(db, user))
    if type:
        stmt = stmt.where(Assessment.type == type)
    if class_id:
        stmt = stmt.where(Assessment.class_id == class_id)
    if subject_id:
        stmt = stmt.where(Assessment.subject_id == subject_id)
    if status:
        stmt = stmt.where(Assessment.status == status)
    if q:
        stmt = stmt.where(Assessment.title.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(Assessment.date.desc().nullslast(), Assessment.id.desc()).offset(p.offset).limit(p.size))
    return {"items": [_out(db, a) for a in items], "total": total, "page": p.page, "size": p.size}


@router.post("", response_model=AssessmentOut, status_code=201)
def create_assessment(body: AssessmentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    c = check_class_access(db, user, body.class_id)
    if not db.get(Subject, body.subject_id):
        raise HTTPException(400, "Пән табылмады")
    t = teacher_of(db, user)
    if not t:
        if user.role == "teacher":
            raise HTTPException(400, "Мұғалім профилі жоқ")
        t = Teacher(user_id=user.id, school_id=user.school_id or c.school_id)
        db.add(t)
        db.flush()
    a = Assessment(**body.model_dump(), teacher_id=t.id, school_id=c.school_id)
    a.versions.append(AssessmentVersion(version_label="1-нұсқа", is_default=True))
    db.add(a)
    db.flush()
    audit(db, user, "assessment.create", "assessment", a.id, after={"title": a.title, "type": a.type}, request=request)
    db.commit()
    return _out(db, a)


@router.get("/answer-types")
def answer_types():
    return list(ANSWER_TYPES)


@router.get("/{assessment_id}")
def get_assessment(assessment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = get_assessment_or_404(db, user, assessment_id)
    v = default_version(a)
    qs = db.scalars(select(Question).where(Question.version_id == v.id).options(selectinload(Question.descriptors))
                    .order_by(Question.number))
    data = _out(db, a).model_dump()
    hide_key = user.role == "student"
    data["versions"] = [{"id": x.id, "label": x.version_label, "is_default": x.is_default,
                         "has_template": bool(x.template_layout)} for x in a.versions]
    data["questions"] = []
    for q in qs:
        qo = QuestionOut.model_validate(q).model_dump()
        if hide_key:
            qo["correct_answer"] = None
        data["questions"].append(qo)
    data["key_total"] = sum(q["max_score"] for q in data["questions"])
    return data


@router.patch("/{assessment_id}", response_model=AssessmentOut)
def update_assessment(assessment_id: int, body: AssessmentUpdate, request: Request, db: Session = Depends(get_db),
                      user: User = Depends(staff)):
    a = get_assessment_or_404(db, user, assessment_id, write=True)
    before = {"title": a.title, "status": a.status, "max_score": a.max_score}
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(a, k, v)
    audit(db, user, "assessment.update", "assessment", a.id, before=before, after=body.model_dump(exclude_none=True,
                                                                                                     mode="json"),
          request=request)
    db.commit()
    return _out(db, a)


@router.delete("/{assessment_id}", status_code=204)
def delete_assessment(assessment_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    a = get_assessment_or_404(db, user, assessment_id, write=True)
    db.delete(a)
    audit(db, user, "assessment.delete", "assessment", assessment_id, before={"title": a.title}, request=request)
    db.commit()


def _apply_question(q: Question, body: QuestionIn) -> None:
    for k, v in body.model_dump(exclude={"descriptors"}).items():
        setattr(q, k, v)
    q.descriptors.clear()
    for d in body.descriptors:
        q.descriptors.append(Descriptor(**d.model_dump()))


@router.put("/{assessment_id}/questions")
def replace_answer_key(assessment_id: int, questions: list[QuestionIn], request: Request,
                       db: Session = Depends(get_db), user: User = Depends(staff)):
    """Replace the whole answer key of the default version (keeps question ids where numbers match)."""
    a = get_assessment_or_404(db, user, assessment_id, write=True)
    nums = [q.number for q in questions]
    if len(nums) != len(set(nums)):
        raise HTTPException(422, "Тапсырма нөмірлері қайталанбауы керек")
    for qi in questions:
        if qi.descriptors and sum(d.points for d in qi.descriptors) - qi.max_score > 1e-9:
            raise HTTPException(422, f"{qi.number}-тапсырма: дескриптор балдарының қосындысы максималды балдан артық")
    v = default_version(a)
    existing = {q.number: q for q in db.scalars(select(Question).where(Question.version_id == v.id)
                                                .options(selectinload(Question.descriptors)))}
    for num, q in existing.items():
        if num not in nums:
            db.delete(q)
    for qi in questions:
        q = existing.get(qi.number) or Question(version_id=v.id)
        _apply_question(q, qi)
        db.add(q)
    a.max_score = sum(q.max_score for q in questions)
    v.template_layout = {}  # layout depends on questions → regenerate
    audit(db, user, "assessment.answer_key", "assessment", a.id, after={"questions": len(questions),
                                                                        "max_score": a.max_score}, request=request)
    db.commit()
    return get_assessment(assessment_id, db, user)


@router.post("/{assessment_id}/questions", status_code=201)
def add_question(assessment_id: int, body: QuestionIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    a = get_assessment_or_404(db, user, assessment_id, write=True)
    v = default_version(a)
    if db.scalar(select(Question).where(Question.version_id == v.id, Question.number == body.number)):
        raise HTTPException(409, "Мұндай нөмірлі тапсырма бар")
    q = Question(version_id=v.id)
    _apply_question(q, body)
    db.add(q)
    a.max_score = (a.max_score or 0) + body.max_score
    v.template_layout = {}
    db.commit()
    return QuestionOut.model_validate(q)


@router.put("/{assessment_id}/questions/{question_id}")
def update_question(assessment_id: int, question_id: int, body: QuestionIn, request: Request,
                    db: Session = Depends(get_db), user: User = Depends(staff)):
    a = get_assessment_or_404(db, user, assessment_id, write=True)
    q = db.get(Question, question_id)
    if not q or q.version.assessment_id != a.id:
        raise HTTPException(404, "Тапсырма табылмады")
    before = QuestionOut.model_validate(q).model_dump(mode="json")
    _apply_question(q, body)
    db.flush()
    a.max_score = sum(x.max_score for x in default_version(a).questions)
    audit(db, user, "question.update", "question", q.id, before=before, after=body.model_dump(mode="json"), request=request)
    db.commit()
    return QuestionOut.model_validate(q)


@router.delete("/{assessment_id}/questions/{question_id}", status_code=204)
def delete_question(assessment_id: int, question_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    a = get_assessment_or_404(db, user, assessment_id, write=True)
    q = db.get(Question, question_id)
    if q and q.version.assessment_id == a.id:
        db.delete(q)
        db.flush()
        a.max_score = sum(x.max_score for x in default_version(a).questions)
        default_version(a).template_layout = {}
        db.commit()


@router.post("/{assessment_id}/questions/import")
async def import_answer_key(assessment_id: int, request: Request, file: UploadFile = File(...),
                            db: Session = Depends(get_db), user: User = Depends(staff)):
    """Import an answer key from JSON (list of questions) or Excel (columns: №, мәтін, түрі, жауап, балл, дескрипторлар)."""
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "Файл тым үлкен")
    name = (file.filename or "").lower()
    try:
        if name.endswith(".json"):
            raw = json.loads(data)
        elif name.endswith(".xlsx"):
            raw = _parse_key_xlsx(data)
        else:
            raise HTTPException(415, "Тек .json немесе .xlsx")
        questions = [QuestionIn.model_validate(x) for x in raw]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(422, f"Файлды оқу мүмкін болмады: {e}") from e
    return replace_answer_key(assessment_id, questions, request, db, user)


def _parse_key_xlsx(data: bytes) -> list[dict]:
    from openpyxl import load_workbook

    ws = load_workbook(io.BytesIO(data), read_only=True).active
    rows = list(ws.iter_rows(values_only=True))
    out = []
    for r in rows[1:]:
        if not r or r[0] is None:
            continue
        num, text, atype, answer, score = r[:5]
        desc_raw = r[5] if len(r) > 5 else None
        ans: object = answer
        if atype == "multiple_choice" and isinstance(answer, str):
            ans = [x.strip() for x in answer.split(",")]
        elif atype == "numeric":
            ans = {"value": float(str(answer).replace(",", "."))}
        descs = []
        if desc_raw:
            for i, line in enumerate(str(desc_raw).splitlines(), 1):
                text_d, _, pts = line.rpartition("|")
                descs.append({"number": i, "text": (text_d or line).strip(), "points": float(pts or 1)})
        out.append({"number": int(num), "text": text or "", "answer_type": atype, "correct_answer": ans,
                    "max_score": float(score), "descriptors": descs})
    return out


# ---------- scan templates ----------
def ensure_layout(db: Session, a: Assessment) -> AssessmentVersion:
    v = default_version(a)
    qs = list(db.scalars(select(Question).where(Question.version_id == v.id).order_by(Question.number)))
    if not qs:
        raise HTTPException(400, "Алдымен бағалау кілтін (тапсырмаларды) енгізіңіз")
    if not v.template_layout or not v.template_layout.get("regions"):
        v.template_layout = build_layout([{"id": q.id, "number": q.number, "text": q.text, "answer_type": q.answer_type,
                                           "options": q.options, "max_score": q.max_score} for q in qs])
        db.commit()
    return v


def template_meta(db: Session, a: Assessment, v: AssessmentVersion) -> dict:
    school = db.get(School, a.school_id)
    return {"title": a.title, "school": school.name if school else "", "subject": a.subject.name,
            "class": a.school_class.name, "version": v.version_label, "date": a.date.isoformat() if a.date else "",
            "max_score": a.max_score}


@router.post("/{assessment_id}/template")
def generate_template(assessment_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    a = get_assessment_or_404(db, user, assessment_id, write=True)
    v = default_version(a)
    v.template_layout = {}
    v = ensure_layout(db, a)
    return {"version_id": v.id, "pages": v.template_layout["pages"], "regions": len(v.template_layout["regions"])}


@router.get("/{assessment_id}/template.pdf")
def template_pdf(assessment_id: int, request: Request, mode: str = Query("students", pattern="^(students|blank)$"),
                 db: Session = Depends(get_db), user: User = Depends(staff)):
    """Printable answer sheets. mode=students: one personalised copy per student (QR has Student ID)."""
    a = get_assessment_or_404(db, user, assessment_id)
    v = ensure_layout(db, a)
    students = None
    if mode == "students":
        students = [{"id": s.id, "full_name": s.full_name} for s in db.scalars(
            select(Student).where(Student.class_id == a.class_id, Student.is_active.is_(True)).order_by(Student.full_name))]
    pdf = render_template_pdf(v.template_layout, template_meta(db, a, v), a.id, v.id, students)
    audit(db, user, "template.download", "assessment", a.id, after={"mode": mode}, request=request, commit=True)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="template-{a.id}-{mode}.pdf"'})


@router.get("/{assessment_id}/students")
def assessment_students(assessment_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    a = get_assessment_or_404(db, user, assessment_id)
    rows = db.scalars(select(Student).where(Student.class_id == a.class_id, Student.is_active.is_(True))
                      .order_by(Student.full_name))
    return [{"id": s.id, "full_name": s.full_name, "gender": s.gender} for s in rows]


@router.get("/{assessment_id}/class")
def assessment_class(assessment_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    a = get_assessment_or_404(db, user, assessment_id)
    c = db.get(SchoolClass, a.class_id)
    return {"id": c.id, "name": c.name, "grade": c.grade}
