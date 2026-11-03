"""Uploads, processing jobs (with WebSocket progress), submissions and page images."""
import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.db import SessionLocal, get_db
from app.core.deps import check_student_access, get_assessment_or_404, get_current_user, staff
from app.core.ratelimit import rate_limit
from app.core.security import decode_token
from app.models import (
    Answer,
    Evaluation,
    ProcessingJob,
    Question,
    Result,
    Student,
    Submission,
    SubmissionPage,
    User,
)
from app.models import (
    File as FileModel,
)
from app.schemas import AssignStudentIn
from app.services import storage
from app.services.audit import audit
from app.services.pipeline import recompute_result
from app.services.pipeline.queue import enqueue_job
from app.services.upload_validation import UploadRejected, validate_upload

router = APIRouter(tags=["processing"])


def job_out(j: ProcessingJob) -> dict:
    return {"id": j.id, "assessment_id": j.assessment_id, "status": j.status, "stage": j.stage, "progress": j.progress,
            "total_pages": j.total_pages, "processed_pages": j.processed_pages, "error": j.error, "stats": j.stats,
            "created_at": j.created_at.isoformat()}


def create_job(db: Session, user: User, assessment, files: list[tuple[str, bytes]], request: Request | None) -> ProcessingJob:
    from app.api.routes.assessments import ensure_layout

    if not any(True for _ in assessment.versions) or not assessment.versions[0].questions:
        raise HTTPException(400, "Алдымен бағалау кілтін енгізіңіз")
    ensure_layout(db, assessment)
    ids = []
    for name, data in files:
        try:
            mime = validate_upload(name, data)
        except UploadRejected as e:
            raise HTTPException(415, str(e)) from e
        f = storage.save_bytes(db, data, mime, "upload", original_name=name[:255], uploaded_by=user.id,
                               school_id=assessment.school_id)
        ids.append(f.id)
    job = ProcessingJob(assessment_id=assessment.id, created_by=user.id, file_ids=ids, status="queued", stage="uploading")
    db.add(job)
    db.flush()
    audit(db, user, "upload.create", "job", job.id, after={"files": [n for n, _ in files]}, request=request)
    db.commit()
    enqueue_job(job.id)
    db.refresh(job)
    return job


@router.post("/assessments/{assessment_id}/uploads", status_code=202,
             dependencies=[Depends(rate_limit("upload", settings.RATE_LIMIT_UPLOAD_PER_MIN))])
async def upload_papers(assessment_id: int, request: Request, files: list[UploadFile] = File(...),
                        db: Session = Depends(get_db), user: User = Depends(staff)):
    a = get_assessment_or_404(db, user, assessment_id, write=True)
    if len(files) > settings.MAX_FILES_PER_UPLOAD:
        raise HTTPException(413, f"Бір реттік жүктеу шегі: {settings.MAX_FILES_PER_UPLOAD} файл")
    payload = []
    for f in files:
        data = await f.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
        payload.append((f.filename or "upload", data))
    return job_out(create_job(db, user, a, payload, request))


@router.get("/assessments/{assessment_id}/jobs")
def list_jobs(assessment_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    get_assessment_or_404(db, user, assessment_id)
    jobs = db.scalars(select(ProcessingJob).where(ProcessingJob.assessment_id == assessment_id)
                      .order_by(ProcessingJob.id.desc()).limit(20))
    return [job_out(j) for j in jobs]


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    j = db.get(ProcessingJob, job_id)
    if not j:
        raise HTTPException(404, "Тапсырма табылмады")
    get_assessment_or_404(db, user, j.assessment_id)
    return job_out(j)


@router.websocket("/ws/jobs/{job_id}")
async def job_ws(ws: WebSocket, job_id: int):
    """Real-time progress. Auth via access_token cookie or ?token=."""
    token = ws.cookies.get("access_token") or ws.query_params.get("token")
    payload = decode_token(token, "access") if token else None
    if not payload:
        await ws.close(code=4401)
        return
    db = SessionLocal()
    try:
        user = db.get(User, int(payload["sub"]))
        j = db.get(ProcessingJob, job_id)
        try:
            if not user or not j:
                raise HTTPException(404)
            get_assessment_or_404(db, user, j.assessment_id)
        except HTTPException:
            await ws.close(code=4404)
            return
    finally:
        db.close()
    await ws.accept()
    last = None
    try:
        while True:
            db = SessionLocal()
            try:
                j = db.get(ProcessingJob, job_id)
                data = job_out(j)
            finally:
                db.close()
            key = (data["stage"], data["progress"], data["status"])
            if key != last:
                await ws.send_json(data)
                last = key
            if data["status"] in ("done", "failed"):
                break
            await asyncio.sleep(0.7)
    except WebSocketDisconnect:
        return
    await ws.close()


# ---------- submissions ----------
def submission_summary(db: Session, s: Submission) -> dict:
    res = db.scalar(select(Result).where(Result.submission_id == s.id))
    counts = dict(db.execute(select(Evaluation.review_status, func.count()).where(Evaluation.submission_id == s.id)
                             .group_by(Evaluation.review_status)).all())
    return {"id": s.id, "assessment_id": s.assessment_id, "student_id": s.student_id,
            "student_name": s.student.full_name if s.student else None, "detected_name": s.detected_name,
            "status": s.status, "detection_method": s.detection_method, "detection_confidence": s.detection_confidence,
            "flags": s.flags, "pages": len(s.pages), "review_counts": counts,
            "total_score": res.total_score if res else None, "max_score": res.max_score if res else None,
            "percent": res.percent if res else None, "level": res.level if res else None,
            "is_final": res.is_final if res else False, "created_at": s.created_at.isoformat()}


@router.get("/assessments/{assessment_id}/submissions")
def list_submissions(assessment_id: int, status: str | None = None, db: Session = Depends(get_db),
                     user: User = Depends(staff)):
    get_assessment_or_404(db, user, assessment_id)
    stmt = select(Submission).where(Submission.assessment_id == assessment_id).options(
        selectinload(Submission.pages), selectinload(Submission.student))
    if status:
        stmt = stmt.where(Submission.status == status)
    subs = list(db.scalars(stmt))
    subs.sort(key=lambda s: (s.student is None, s.student.full_name if s.student else "", s.id))
    return [submission_summary(db, s) for s in subs]


def _check_submission(db: Session, user: User, submission_id: int) -> Submission:
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(404, "Жұмыс табылмады")
    if user.role == "student":
        if not s.student or s.student.user_id != user.id:
            raise HTTPException(404, "Жұмыс табылмады")
    else:
        get_assessment_or_404(db, user, s.assessment_id)
    return s


def evaluation_out(ev: Evaluation | None) -> dict | None:
    if not ev:
        return None
    return {"id": ev.id, "method": ev.method, "score": ev.score, "max_score": ev.max_score,
            "ai_suggested_score": ev.ai_suggested_score, "confidence": ev.confidence, "status": ev.status,
            "review_status": ev.review_status, "reasoning": ev.reasoning, "error_category": ev.error_category,
            "expected_answer": ev.expected_answer, "teacher_comment": ev.teacher_comment,
            "items": [{"id": it.id, "descriptor_id": it.descriptor_id,
                       "number": it.descriptor.number if it.descriptor else None,
                       "text": it.descriptor.text if it.descriptor else None,
                       "points": it.descriptor.points if it.descriptor else None, "met": it.met,
                       "points_awarded": it.points_awarded, "reason": it.reason} for it in ev.items],
            "reviews": [{"action": r.action, "old_score": r.old_score, "new_score": r.new_score, "comment": r.comment,
                         "reviewer_id": r.reviewer_id, "created_at": r.created_at.isoformat()} for r in ev.reviews]}


@router.get("/submissions/{submission_id}")
def get_submission(submission_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _check_submission(db, user, submission_id)
    answers = list(db.scalars(select(Answer).where(Answer.submission_id == s.id).options(
        selectinload(Answer.evaluation).selectinload(Evaluation.items), selectinload(Answer.question))))
    answers.sort(key=lambda a: a.question.number)
    res = db.scalar(select(Result).where(Result.submission_id == s.id))
    data = submission_summary(db, s)
    data["pages_detail"] = [{"id": p.id, "page_number": p.page_number, "width": p.width, "height": p.height,
                             "quality": p.quality_score, "status": p.status, "preprocessing": p.preprocessing,
                             "qr": p.qr_payload} for p in s.pages]
    student_view = user.role == "student"
    data["answers"] = [{
        "id": a.id, "question_id": a.question_id, "number": a.question.number, "question_text": a.question.text,
        "answer_type": a.question.answer_type, "max_score": a.question.max_score, "page_id": a.page_id, "bbox": a.bbox,
        "detected_answer": a.detected_answer, "ocr_confidence": round(a.ocr_confidence * 100, 1), "flags": a.flags,
        "evaluation": evaluation_out(a.evaluation) if not student_view or (res and res.is_final) else None,
    } for a in answers]
    data["result"] = None if not res else {
        "id": res.id, "total_score": res.total_score, "max_score": res.max_score, "percent": res.percent,
        "level": res.level, "feedback": res.feedback, "strengths": res.strengths, "weaknesses": res.weaknesses,
        "is_final": res.is_final}
    return data


@router.patch("/submissions/{submission_id}/student")
def assign_student(submission_id: int, body: AssignStudentIn, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(staff)):
    """«Оқушыны таңдаңыз»: teacher resolves an unidentified work."""
    s = _check_submission(db, user, submission_id)
    st = db.get(Student, body.student_id)
    if not st:
        raise HTTPException(404, "Оқушы табылмады")
    check_student_access(db, user, st)
    other = db.scalar(select(Submission).where(Submission.assessment_id == s.assessment_id,
                                               Submission.student_id == st.id, Submission.id != s.id))
    if other:
        raise HTTPException(409, "Бұл оқушының жұмысы бұрыннан бар. Алдымен оны жойыңыз.")
    before = {"student_id": s.student_id}
    s.student_id = st.id
    s.detection_method = "manual"
    s.detection_confidence = 1.0
    s.flags = [f for f in (s.flags or []) if f != "student_unknown"]
    recompute_result(db, s)
    audit(db, user, "submission.assign_student", "submission", s.id, before=before, after={"student_id": st.id},
          request=request)
    db.commit()
    return submission_summary(db, s)


@router.delete("/submissions/{submission_id}", status_code=204)
def delete_submission(submission_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    s = _check_submission(db, user, submission_id)
    db.delete(s)
    audit(db, user, "submission.delete", "submission", submission_id, request=request)
    db.commit()


@router.get("/pages/{page_id}/image")
def page_image(page_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.get(SubmissionPage, page_id)
    if not p or not p.submission_id:
        raise HTTPException(404, "Бет табылмады")
    _check_submission(db, user, p.submission_id)
    f = db.get(FileModel, p.file_id)
    return Response(storage.read_file(f), media_type=f.mime, headers={"Cache-Control": "private, max-age=3600"})


@router.get("/pages/{page_id}/ocr")
def page_ocr(page_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    p = db.get(SubmissionPage, page_id)
    if not p or not p.submission_id:
        raise HTTPException(404, "Бет табылмады")
    _check_submission(db, user, p.submission_id)
    o = p.ocr
    return {"provider": o.provider, "text": o.full_text, "mean_confidence": o.mean_confidence,
            "words": o.words} if o else None


@router.get("/questions/{question_id}/answers")
def answers_for_question(question_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(404)
    get_assessment_or_404(db, user, q.version.assessment_id)
    rows = db.scalars(select(Answer).where(Answer.question_id == q.id).options(selectinload(Answer.evaluation)))
    return [{"answer_id": a.id, "submission_id": a.submission_id, "detected_answer": a.detected_answer,
             "score": a.evaluation.score if a.evaluation else None} for a in rows]
