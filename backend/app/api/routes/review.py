"""Teacher review: accept / override / re-check, batch approval, finalisation. Teacher's decision is authoritative."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.deps import get_assessment_or_404, staff
from app.models import Answer, Evaluation, ManualReview, Question, Result, Submission, User
from app.schemas import AcceptIn, BatchApproveIn, FeedbackIn, OverrideIn, RecheckIn
from app.services.ai.service import AIService, get_provider
from app.services.audit import audit
from app.services.pipeline import evaluate_and_store, recompute_result, thresholds_for
from app.services.scoring import ScoringEngine

router = APIRouter(tags=["review"])


def _load(db: Session, user: User, evaluation_id: int) -> tuple[Evaluation, Submission]:
    ev = db.get(Evaluation, evaluation_id)
    if not ev:
        raise HTTPException(404, "Бағалау табылмады")
    sub = db.get(Submission, ev.submission_id)
    get_assessment_or_404(db, user, sub.assessment_id, write=False)
    if user.role == "student":
        raise HTTPException(403)
    return ev, sub


def _snapshot(ev: Evaluation) -> dict:
    return {"score": ev.score, "status": ev.status, "review_status": ev.review_status}


@router.get("/review/queue")
def review_queue(assessment_id: int | None = None, include_medium: bool = True, db: Session = Depends(get_db),
                 user: User = Depends(staff)):
    statuses = ["needs_review", "medium"] if include_medium else ["needs_review"]
    stmt = (select(Evaluation, Answer, Submission, Question)
            .join(Answer, Answer.id == Evaluation.answer_id)
            .join(Submission, Submission.id == Evaluation.submission_id)
            .join(Question, Question.id == Evaluation.question_id)
            .where(Evaluation.review_status.in_(statuses)))
    if assessment_id:
        get_assessment_or_404(db, user, assessment_id)
        stmt = stmt.where(Submission.assessment_id == assessment_id)
    out = []
    for ev, ans, sub, q in db.execute(stmt.order_by(Evaluation.confidence).limit(500)):
        try:
            get_assessment_or_404(db, user, sub.assessment_id)
        except HTTPException:
            continue
        out.append({"evaluation_id": ev.id, "submission_id": sub.id, "assessment_id": sub.assessment_id,
                    "student_name": sub.student.full_name if sub.student else None, "question_number": q.number,
                    "answer_type": q.answer_type, "detected_answer": ans.detected_answer,
                    "expected_answer": ev.expected_answer, "score": ev.score, "max_score": ev.max_score,
                    "confidence": ev.confidence, "status": ev.status, "review_status": ev.review_status,
                    "reasoning": ev.reasoning, "flags": ans.flags})
    return out


@router.post("/evaluations/{evaluation_id}/accept")
def accept(evaluation_id: int, body: AcceptIn, request: Request, db: Session = Depends(get_db),
           user: User = Depends(staff)):
    ev, sub = _load(db, user, evaluation_id)
    before = _snapshot(ev)
    ev.review_status = "approved"
    if ev.status == "doubtful":
        ev.status = "correct" if ev.score >= ev.max_score else ("incorrect" if ev.score == 0 else "partial")
    if body.comment:
        ev.teacher_comment = body.comment
    db.add(ManualReview(evaluation_id=ev.id, reviewer_id=user.id, action="accept", old_score=ev.score,
                        new_score=ev.score, comment=body.comment))
    recompute_result(db, sub)
    audit(db, user, "evaluation.accept", "evaluation", ev.id, before=before, after=_snapshot(ev), request=request)
    db.commit()
    return {"ok": True, "evaluation": _snapshot(ev)}


@router.post("/evaluations/{evaluation_id}/override")
def override(evaluation_id: int, body: OverrideIn, request: Request, db: Session = Depends(get_db),
             user: User = Depends(staff)):
    ev, sub = _load(db, user, evaluation_id)
    if body.score > ev.max_score + 1e-9:
        raise HTTPException(422, f"Балл {ev.max_score}-тан аспауы керек")
    before = _snapshot(ev)
    old = ev.score
    if body.descriptor_items:
        by_id = {it.descriptor_id: it for it in ev.items}
        for d in body.descriptor_items:
            it = by_id.get(d.get("descriptor_id"))
            if it:
                it.met = bool(d.get("met"))
                it.points_awarded = it.descriptor.points if it.met and it.descriptor else 0.0
    ev.score = body.score
    ev.status = body.status or ("correct" if body.score >= ev.max_score else "incorrect" if body.score == 0 else "partial")
    ev.review_status = "overridden" if abs(old - body.score) > 1e-9 else "approved"
    ev.method = "manual" if abs(old - body.score) > 1e-9 else ev.method
    ev.teacher_comment = body.comment
    if ev.status == "correct":
        ev.error_category = None
    db.add(ManualReview(evaluation_id=ev.id, reviewer_id=user.id, action="override", old_score=old,
                        new_score=body.score, comment=body.comment))
    recompute_result(db, sub)
    audit(db, user, "evaluation.override", "evaluation", ev.id, before=before,
          after={**_snapshot(ev), "comment": body.comment}, request=request)
    db.commit()
    return {"ok": True, "evaluation": _snapshot(ev)}


@router.post("/evaluations/{evaluation_id}/recheck")
def recheck(evaluation_id: int, body: RecheckIn, request: Request, db: Session = Depends(get_db),
            user: User = Depends(staff)):
    """Re-run evaluation, optionally with a corrected transcription or a different AI provider."""
    ev, sub = _load(db, user, evaluation_id)
    ans = db.get(Answer, ev.answer_id)
    q = db.scalar(select(Question).where(Question.id == ev.question_id).options(selectinload(Question.descriptors)))
    before = _snapshot(ev)
    if body.detected_answer is not None:
        ans.detected_answer = body.detected_answer
        ans.ocr_confidence = 1.0  # teacher-confirmed text
        ans.flags = [f for f in (ans.flags or []) if f not in ("empty", "unreadable", "not_detected", "error")]
    try:
        ai = AIService(get_provider(body.provider) if body.provider else None)
    except Exception as e:
        raise HTTPException(400, f"AI провайдері қолжетімсіз: {e}") from e
    from app.models import Assessment

    engine = ScoringEngine(thresholds_for(db.get(Assessment, sub.assessment_id)))
    old = ev.score
    ev = evaluate_and_store(db, ans, q, ai, engine)
    db.add(ManualReview(evaluation_id=ev.id, reviewer_id=user.id, action="recheck", old_score=old, new_score=ev.score,
                        comment=f"Қайта тексеру{' (мәтін түзетілді)' if body.detected_answer is not None else ''}"))
    recompute_result(db, sub)
    audit(db, user, "evaluation.recheck", "evaluation", ev.id, before=before, after=_snapshot(ev), request=request)
    db.commit()
    from app.api.routes.processing import evaluation_out

    return {"ok": True, "evaluation": evaluation_out(ev), "detected_answer": ans.detected_answer}


@router.post("/assessments/{assessment_id}/approve-confident")
def approve_confident(assessment_id: int, body: BatchApproveIn, request: Request, db: Session = Depends(get_db),
                      user: User = Depends(staff)):
    """«Барлық сенімді нәтижелерді бекіту»."""
    get_assessment_or_404(db, user, assessment_id, write=True)
    statuses = ["auto_approved", "medium"] if body.include_medium else ["auto_approved"]
    evs = list(db.scalars(select(Evaluation).join(Submission, Submission.id == Evaluation.submission_id).where(
        Submission.assessment_id == assessment_id, Submission.student_id.is_not(None),
        Evaluation.review_status.in_(statuses), Evaluation.confidence >= body.min_confidence)))
    touched = set()
    for ev in evs:
        ev.review_status = "approved"
        db.add(ManualReview(evaluation_id=ev.id, reviewer_id=user.id, action="accept", old_score=ev.score,
                            new_score=ev.score, comment="batch"))
        touched.add(ev.submission_id)
    for sid in touched:
        recompute_result(db, db.get(Submission, sid))
    audit(db, user, "evaluation.batch_approve", "assessment", assessment_id,
          after={"approved": len(evs), "min_confidence": body.min_confidence}, request=request)
    db.commit()
    remaining = db.query(Evaluation).join(Submission, Submission.id == Evaluation.submission_id).filter(
        Submission.assessment_id == assessment_id, Evaluation.review_status.in_(["needs_review", "medium"])).count()
    return {"approved": len(evs), "remaining": remaining}


@router.post("/submissions/{submission_id}/approve")
def approve_submission(submission_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    """Finalise one student's work (requires student identified). Pending answers are accepted as-is."""
    sub = db.get(Submission, submission_id)
    if not sub:
        raise HTTPException(404)
    get_assessment_or_404(db, user, sub.assessment_id, write=True)
    if not sub.student_id:
        raise HTTPException(400, "Алдымен оқушыны таңдаңыз")
    for ev in db.scalars(select(Evaluation).where(Evaluation.submission_id == sub.id)):
        if ev.review_status not in ("approved", "overridden"):
            ev.review_status = "approved"
            db.add(ManualReview(evaluation_id=ev.id, reviewer_id=user.id, action="accept", old_score=ev.score,
                                new_score=ev.score, comment="submission approved"))
    res = recompute_result(db, sub)
    res.is_final, res.approved_by, res.approved_at = True, user.id, datetime.now(UTC)
    sub.status = "approved"
    audit(db, user, "submission.approve", "submission", sub.id, after={"total": res.total_score}, request=request)
    db.commit()
    return {"ok": True, "total_score": res.total_score, "percent": res.percent}


@router.post("/assessments/{assessment_id}/approve-all")
def approve_all(assessment_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    """«Барлығын бекіту»: finalise every identified work that has no unresolved 'needs_review' answers."""
    a = get_assessment_or_404(db, user, assessment_id, write=True)
    approved, skipped = 0, []
    for sub in db.scalars(select(Submission).where(Submission.assessment_id == assessment_id)):
        pending = db.query(Evaluation).filter(Evaluation.submission_id == sub.id,
                                              Evaluation.review_status == "needs_review").count()
        if not sub.student_id or pending:
            skipped.append(sub.id)
            continue
        approve_submission(sub.id, request, db, user)
        approved += 1
    if not skipped:
        a.status = "completed"
        db.commit()
    return {"approved": approved, "skipped": skipped}


@router.patch("/results/{result_id}/feedback")
def edit_feedback(result_id: int, body: FeedbackIn, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(staff)):
    res = db.get(Result, result_id)
    if not res:
        raise HTTPException(404)
    get_assessment_or_404(db, user, res.assessment_id, write=True)
    before = {"feedback": res.feedback}
    res.feedback = body.feedback
    res.feedback_edited = True
    audit(db, user, "result.feedback", "result", res.id, before=before, after={"feedback": body.feedback},
          request=request)
    db.commit()
    return {"ok": True}
