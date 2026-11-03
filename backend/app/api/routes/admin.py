"""Audit log, runtime settings, health, demo helpers."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import admins, get_assessment_or_404, staff
from app.core.pagination import PageParams
from app.models import AuditLog, Question, Student, User
from app.schemas import SettingsIn
from app.services import app_settings
from app.services.audit import audit

router = APIRouter(tags=["admin"])


@router.get("/audit")
def audit_logs(action: str | None = None, entity_type: str | None = None, user_id: int | None = None,
               p: PageParams = Depends(), db: Session = Depends(get_db), user: User = Depends(admins)):
    stmt = select(AuditLog)
    if user.role == "school_admin":
        stmt = stmt.where(AuditLog.school_id == user.school_id)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"{action}%"))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.id.desc()).offset(p.offset).limit(p.size))
    names = dict(db.execute(select(User.id, User.full_name)).all())
    return {"items": [{"id": r.id, "created_at": r.created_at.isoformat(), "user": names.get(r.user_id),
                       "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id, "before": r.before,
                       "after": r.after, "ip": r.ip} for r in rows], "total": total, "page": p.page, "size": p.size}


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), user: User = Depends(staff)):
    return app_settings.current(db)


@router.put("/settings")
def put_settings(body: SettingsIn, request: Request, db: Session = Depends(get_db), user: User = Depends(admins)):
    before = app_settings.current(db)
    if user.role != "admin":  # school admins may only tighten privacy / thresholds
        body.values = {k: v for k, v in body.values.items() if k in {"AI_SEND_STUDENT_NAMES", "AI_SEND_IMAGES",
                                                                      "CONFIDENCE_HIGH", "CONFIDENCE_MEDIUM",
                                                                      "AUTO_APPROVE_HIGH_CONFIDENCE"}}
    out = app_settings.update(db, body.values)
    audit(db, user, "settings.update", "settings", None, before={k: before.get(k) for k in body.values},
          after=body.values, request=request)
    db.commit()
    return out


@router.get("/health", tags=["health"])
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "environment": settings.ENVIRONMENT, "queue": settings.QUEUE_MODE,
            "ocr": settings.OCR_PROVIDER, "ai": settings.AI_PROVIDER, "demo": settings.SEED_DEMO}


# ---------- demo flow ----------
def _demo_pdf(db: Session, assessment_id: int, user: User) -> bytes:
    from app.api.routes.assessments import default_version, ensure_layout, template_meta
    from app.seed.demo_scans import generate_demo_scan

    a = get_assessment_or_404(db, user, assessment_id)
    v = ensure_layout(db, a)
    students = [{"id": s.id, "full_name": s.full_name} for s in db.scalars(
        select(Student).where(Student.class_id == a.class_id, Student.is_active.is_(True)).order_by(Student.full_name))]
    if not students:
        raise HTTPException(400, "Сыныпта оқушы жоқ")
    qs = list(db.scalars(select(Question).where(Question.version_id == default_version(a).id).order_by(Question.number)))
    qdefs = [_demo_qdef(q) for q in qs]
    return generate_demo_scan(v.template_layout, template_meta(db, a, v), a.id, v.id, students, qdefs, seed=a.id)


def _demo_qdef(q: Question) -> dict:
    """Use curated answers from the demo dataset when available, otherwise derive plausible ones."""
    from app.seed.demo_data import MATH_BJB

    for d in MATH_BJB["questions"]:
        if d["text"] == q.text:
            return d
    ca = q.correct_answer
    val = ca.get("value") if isinstance(ca, dict) and "value" in ca else ca
    right = [str(val)] if not isinstance(val, (list, dict)) else [", ".join(map(str, val))]
    if q.answer_type in ("single_choice", "multiple_choice"):
        return {"number": q.number, "answer_type": q.answer_type, "correct_answer": ca,
                "wrong": ["C"] if q.answer_type == "single_choice" else [["B"]]}
    return {"number": q.number, "answer_type": q.answer_type, "correct_answer": ca, "right": right, "wrong": ["?"]}


@router.get("/demo/sample-scan/{assessment_id}")
def demo_sample_scan(assessment_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    """A realistic 'scanned' PDF of the whole class (QR sheets filled in, rotated, shadowed, noisy)."""
    pdf = _demo_pdf(db, assessment_id, user)
    audit(db, user, "demo.sample_scan", "assessment", assessment_id, request=request, commit=True)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="demo-scan-{assessment_id}.pdf"'})


@router.post("/demo/run/{assessment_id}", status_code=202)
def demo_run(assessment_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    """One click: generate the demo scan and push it through the real pipeline."""
    from app.api.routes.processing import create_job, job_out

    a = get_assessment_or_404(db, user, assessment_id, write=True)
    pdf = _demo_pdf(db, assessment_id, user)
    return job_out(create_job(db, user, a, [(f"demo-scan-{a.id}.pdf", pdf)], request))
