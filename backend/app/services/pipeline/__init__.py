"""Processing pipeline: Upload → Job → split → preprocess → identify → group → extract → evaluate → score → result.

Every failure is contained: a broken page or a failed OCR/AI call marks only that page/answer as
`manual_review_required`; the job itself continues.
"""
import logging
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime

import cv2
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import (
    AIEvaluation,
    Answer,
    Assessment,
    AssessmentVersion,
    Evaluation,
    EvaluationItem,
    File,
    OCRResult,
    ProcessingJob,
    Question,
    Result,
    Student,
    Submission,
    SubmissionPage,
)
from app.services import storage
from app.services.ai.service import AIService
from app.services.detection.extract import Extracted, extract_from_template
from app.services.detection.qr import find_planit_qr
from app.services.detection.structure import detect_tasks
from app.services.detection.student import match_student
from app.services.evaluation.dispatcher import evaluate_answer
from app.services.feedback import build_feedback
from app.services.ocr import OCRService
from app.services.pipeline.pdf import CorruptedFile, split_pages
from app.services.preprocessing import encode_jpeg, preprocess
from app.services.scoring import ScoringEngine, level_for, percent

log = logging.getLogger(__name__)

STAGES = ["uploading", "preprocessing", "ocr", "detecting_tasks", "extracting_answers", "evaluating", "done"]
STAGE_WEIGHT = {"uploading": 0, "preprocessing": 5, "ocr": 15, "detecting_tasks": 55, "extracting_answers": 65,
                "evaluating": 75, "done": 100}


@dataclass
class PageWork:
    index: int
    source_file_id: int
    source_page: int
    page_id: int | None = None
    qr: dict | None = None
    version_id: int | None = None
    page_number: int | None = None
    aligned: bool = False
    student_id: int | None = None
    student_conf: float = 0.0
    detected_name: str | None = None
    extracted: list[Extracted] = field(default_factory=list)
    error: str | None = None
    ocr_text: str = ""


def _set(db: Session, job: ProcessingJob, stage: str | None = None, progress: float | None = None, **kw) -> None:
    if stage:
        job.stage = stage
    if progress is not None:
        job.progress = round(min(100.0, progress), 1)
    for k, v in kw.items():
        setattr(job, k, v)
    db.commit()


def _layouts(assessment: Assessment) -> dict[int, dict]:
    return {v.id: v.template_layout for v in assessment.versions if v.template_layout}


def _crop_norm(gray, box: dict):
    H, W = gray.shape
    return gray[int(box["y"] * H):int((box["y"] + box["h"]) * H), int(box["x"] * W):int((box["x"] + box["w"]) * W)]


def _process_page(pw: PageWork, img, assessment: Assessment, roster: list[tuple[int, str]],
                  questions_by_version: dict[int, list[Question]], ocr: OCRService) -> tuple[PageWork, object, dict, object]:
    """CPU-heavy part executed in a worker thread. Returns (work, processed gray, preprocessing info, ocr output)."""
    layouts = _layouts(assessment)
    default_version = next((v.id for v in assessment.versions if v.is_default), assessment.versions[0].id)
    raw_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    qr, code = find_planit_qr(raw_gray)
    if qr and qr["assessment_id"] == assessment.id and qr["version_id"] in layouts:
        pw.qr, pw.version_id, pw.page_number = qr, qr["version_id"], qr["page"]
        if qr.get("student_id") and any(s == qr["student_id"] for s, _ in roster):
            pw.student_id, pw.student_conf = qr["student_id"], 1.0
    elif qr:
        pw.error = "foreign_qr"  # QR from another assessment
    layout = layouts.get(pw.version_id or default_version)
    pre = preprocess(img, layout=layout, detect_orientation=None if layout else ocr.orientation)
    pw.aligned = pre.aligned
    if pre.aligned and pw.qr is None:
        # QR may be readable only after alignment
        qr2, _ = find_planit_qr(pre.image)
        if qr2 and qr2["assessment_id"] == assessment.id:
            pw.qr, pw.version_id, pw.page_number = qr2, qr2["version_id"], qr2["page"]
            if qr2.get("student_id"):
                pw.student_id, pw.student_conf = qr2["student_id"], 1.0
    info = {"ops": pre.ops, "quality": pre.quality, "details": pre.details}
    ocr_out = None
    version_id = pw.version_id or default_version
    questions = questions_by_version.get(version_id, [])
    if pre.aligned and layout:
        page_no = pw.page_number or 1
        q_ids = {q.number: q.id for q in questions}
        regions = [{**r, "question_id": q_ids.get(r["number"], r.get("question_id"))}
                   for r in layout["regions"] if r["page"] == page_no]
        pw.extracted = extract_from_template(pre.image, regions, ocr)
        if page_no == 1 and not pw.student_id:
            try:
                name_out = ocr.recognize(_crop_norm(pre.image, layout["name_field"]), mode="line")
                pw.ocr_text = "Аты-жөні: " + name_out.text
                ocr_out = name_out
            except Exception as e:
                pw.error = f"ocr_failed: {e}"[:200]
    else:
        try:
            ocr_out = ocr.recognize(pre.image, mode="page")
            pw.ocr_text = ocr_out.text
            H, W = pre.image.shape
            pw.extracted = detect_tasks(ocr_out, W, H, questions)
        except Exception as e:
            pw.error = f"ocr_failed: {e}"[:200]
    if not pw.student_id and pw.ocr_text:
        sid, conf, name = match_student(pw.ocr_text, roster)
        pw.student_id, pw.student_conf, pw.detected_name = sid, conf, name
    return pw, pre.image, info, ocr_out


def run_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        from app.services import app_settings

        app_settings.apply(db)  # workers pick up admin-edited AI/OCR settings
        _run(db, job_id)
    except Exception as e:  # last-resort guard: never leave a job "running"
        log.exception("job %s crashed", job_id)
        db.rollback()
        job = db.get(ProcessingJob, job_id)
        if job:
            job.status, job.error = "failed", f"{e!r}\n{traceback.format_exc()[-1500:]}"
            db.commit()
    finally:
        db.close()


def _run(db: Session, job_id: int) -> None:
    job = db.get(ProcessingJob, job_id)
    assessment = db.scalar(select(Assessment).where(Assessment.id == job.assessment_id).options(
        selectinload(Assessment.versions).selectinload(AssessmentVersion.questions).selectinload(Question.descriptors)))
    _set(db, job, "preprocessing", 2, status="running")
    roster = [(s.id, s.full_name) for s in db.scalars(select(Student).where(
        Student.class_id == assessment.class_id, Student.is_active.is_(True)))]
    questions_by_version = {v.id: list(v.questions) for v in assessment.versions}
    ocr = OCRService()

    # 1. split
    pages: list[tuple[PageWork, object]] = []
    errors: list[str] = []
    for fid in job.file_ids:
        f = db.get(File, fid)
        try:
            imgs = split_pages(storage.read_file(f), f.mime, settings.PDF_DPI)
        except CorruptedFile as e:
            errors.append(f"{f.original_name}: {e}")
            continue
        for i, img in enumerate(imgs):
            pages.append((PageWork(len(pages), fid, i), img))
    total = len(pages)
    _set(db, job, "ocr", 5, total_pages=total)
    if total == 0:
        _set(db, job, "done", 100, status="failed", error="; ".join(errors) or "Бет табылмады")
        return

    # 2. per-page work in parallel (tesseract runs as subprocess → real parallelism)
    results: list[tuple[PageWork, object, dict, object]] = [None] * total  # type: ignore
    workers = max(1, min(int(os.environ.get("PIPELINE_WORKERS", os.cpu_count() or 2)), total))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_process_page, pw, img, assessment, roster, questions_by_version, ocr): pw.index
                for pw, img in pages}
        done = 0
        for fut in as_completed(futs):
            idx = futs[fut]
            try:
                results[idx] = fut.result()
            except Exception as e:
                pw = pages[idx][0]
                pw.error = f"page_failed: {e!r}"[:300]
                results[idx] = (pw, cv2.cvtColor(pages[idx][1], cv2.COLOR_BGR2GRAY), {"ops": [], "quality": 0}, None)
            done += 1
            _set(db, job, "ocr", 5 + 50 * done / total, processed_pages=done)
    del pages

    # persist pages
    _set(db, job, "detecting_tasks", 56)
    for pw, gray, info, ocr_out in results:
        f = storage.save_bytes(db, encode_jpeg(gray, 82), "image/jpeg", "page", school_id=assessment.school_id)
        page_status = "error" if pw.error else ("low_quality" if (info.get("quality") or 0) < 0.35 else "ok")
        sp = SubmissionPage(job_id=job.id, file_id=f.id, original_file_id=pw.source_file_id,
                            page_number=pw.page_number or 1, source_page_index=pw.source_page, qr_payload=pw.qr,
                            quality_score=info.get("quality"), preprocessing=info, width=gray.shape[1],
                            height=gray.shape[0], status=page_status)
        db.add(sp)
        db.flush()
        pw.page_id = sp.id
        if ocr_out is not None:
            db.add(OCRResult(page_id=sp.id, provider=ocr_out.provider, language=settings.OCR_LANGUAGES,
                             full_text=ocr_out.text[:20000],
                             words=[{"text": w.text, "conf": round(w.conf, 3), "bbox": list(w.bbox)} for w in ocr_out.words[:3000]],
                             mean_confidence=ocr_out.mean_confidence, duration_ms=ocr_out.duration_ms))
    db.commit()

    # 3. group pages into submissions
    groups = group_pages([r[0] for r in results])
    _set(db, job, "extracting_answers", 65, stats={"submissions": len(groups), "file_errors": errors})

    # 4-6. answers → evaluation → scoring → results
    ai = AIService()
    engine = ScoringEngine(thresholds_for(assessment))
    default_version = next((v.id for v in assessment.versions if v.is_default), assessment.versions[0].id)
    created = 0
    for gi, g in enumerate(groups):
        version_id = g["version_id"] or default_version
        sub = Submission(assessment_id=assessment.id, version_id=version_id, student_id=g["student_id"], job_id=job.id,
                         status="processing", detection_method=g["method"], detection_confidence=g["confidence"],
                         detected_name=g["detected_name"], flags=g["flags"])
        # same student uploaded again → replace the previous submission
        if g["student_id"]:
            for old in db.scalars(select(Submission).where(Submission.assessment_id == assessment.id,
                                                           Submission.student_id == g["student_id"])):
                db.delete(old)
            db.flush()
        db.add(sub)
        db.flush()
        for pw in g["pages"]:
            sp = db.get(SubmissionPage, pw.page_id)
            sp.submission_id = sub.id
        extracted: dict[int, tuple[Extracted, PageWork]] = {}
        for pw in g["pages"]:
            for ex in pw.extracted:
                if ex.number not in extracted or (not extracted[ex.number][0].text and ex.text):
                    extracted[ex.number] = (ex, pw)
        for q in questions_by_version.get(version_id, []):
            ex, pw = extracted.get(q.number, (None, None))
            flags = list(ex.flags) if ex else ["not_detected"]
            if not ex and any(p.error for p in g["pages"]):
                flags.append("error")
            ans = Answer(submission_id=sub.id, question_id=q.id, page_id=pw.page_id if pw else None,
                         bbox=ex.bbox if ex else None, detected_answer=ex.text if ex else "",
                         raw_text=ex.raw_text if ex else "", ocr_confidence=ex.confidence if ex else 0.0, flags=flags)
            db.add(ans)
            db.flush()
            evaluate_and_store(db, ans, q, ai, engine, g["student_id"] is None)
        db.flush()
        recompute_result(db, sub)
        db.commit()
        created += 1
        _set(db, job, "evaluating", 75 + 24 * (gi + 1) / max(1, len(groups)))

    stats = job_stats(db, job.id)
    stats.update({"submissions": created, "file_errors": errors})
    if assessment.status == "draft":
        assessment.status = "active"
    _set(db, job, "done", 100, status="done", stats=stats)


def thresholds_for(assessment: Assessment):
    from app.services.scoring import Thresholds

    s = assessment.settings or {}
    return Thresholds(high=float(s.get("confidence_high", settings.CONFIDENCE_HIGH)),
                      medium=float(s.get("confidence_medium", settings.CONFIDENCE_MEDIUM)),
                      auto_approve=bool(s.get("auto_approve", settings.AUTO_APPROVE_HIGH_CONFIDENCE)))


def group_pages(pages: list[PageWork]) -> list[dict]:
    """Split a stream of pages into per-student submissions.

    Priority: QR student id → QR page numbers (blank template) → detected name → sequential order.
    """
    groups: list[dict] = []
    by_student: dict[int, dict] = {}
    current: dict | None = None

    def new_group(pw: PageWork, method: str) -> dict:
        g = {"student_id": pw.student_id, "version_id": pw.version_id, "pages": [], "method": method,
             "confidence": pw.student_conf, "detected_name": pw.detected_name, "flags": []}
        groups.append(g)
        if pw.student_id:
            by_student[pw.student_id] = g
        return g

    for pw in pages:
        if pw.qr and pw.qr.get("student_id") and pw.student_id:
            g = by_student.get(pw.student_id) or new_group(pw, "qr")
            current = g
        elif pw.qr:  # blank template: page numbers drive splitting
            if pw.page_number == 1 or current is None:
                if pw.student_id and pw.student_id in by_student:
                    current = by_student[pw.student_id]
                    current["flags"].append("duplicate_student_pages")
                else:
                    current = new_group(pw, "name_ocr" if pw.student_id else "unknown")
        else:  # no template: a recognised name starts a new work
            if current is None or (pw.student_id and pw.student_id != current["student_id"]):
                if pw.student_id and pw.student_id in by_student:
                    current = by_student[pw.student_id]
                else:
                    current = new_group(pw, "name_ocr" if pw.student_id else "unknown")
        if any(p.page_number == pw.page_number and pw.page_number and p.qr for p in current["pages"]):
            current["flags"].append("mixed_pages")
        current["pages"].append(pw)
        if pw.error:
            current["flags"].append(pw.error.split(":")[0])
    for g in groups:
        g["pages"].sort(key=lambda p: (p.page_number or 0, p.index))
        if not g["student_id"]:
            g["flags"].append("student_unknown")
        g["flags"] = sorted(set(g["flags"]))
    return groups


def evaluate_and_store(db: Session, ans: Answer, q: Question, ai: AIService, engine: ScoringEngine,
                       student_unknown: bool = False) -> Evaluation:
    proposal = evaluate_answer(q, ans.detected_answer or "", list(ans.flags or []), ai)
    if proposal.ai_record:
        r = proposal.ai_record
        db.add(AIEvaluation(answer_id=ans.id, provider=r.get("provider", ""), model=r.get("model"),
                            request_hash=r.get("request_hash"), response=r.get("response"),
                            raw_response=r.get("raw_response"), schema_valid=bool(r.get("schema_valid")),
                            latency_ms=r.get("latency_ms", 0), error=r.get("error")))
    flags = list(ans.flags or [])
    if "not_detected" in flags:
        flags.append("manual_review_required")
    res = engine.score(q, proposal, ans.ocr_confidence, flags)
    ev = ans.evaluation or db.scalar(select(Evaluation).where(Evaluation.answer_id == ans.id))
    if ev is None:
        ev = Evaluation(answer_id=ans.id, question_id=q.id, submission_id=ans.submission_id)
        db.add(ev)
    else:
        ev.items.clear()
    ev.method = proposal.method
    ev.score, ev.max_score = res.score, res.max_score
    ev.ai_suggested_score = proposal.suggested_score
    ev.confidence, ev.status, ev.review_status = res.confidence, res.status, res.review_status
    ev.reasoning, ev.error_category, ev.expected_answer = res.reasoning, res.error_category, proposal.expected_answer
    if "not_detected" in (ans.flags or []):
        ev.reasoning = "Тапсырма/жауап аймағы анықталмады. Қолмен тексеру қажет."
    db.flush()
    for it in res.items:
        ev.items.append(EvaluationItem(descriptor_id=it.descriptor_id, met=it.met, points_awarded=it.points_awarded,
                                       reason=it.reason, confidence=it.confidence))
    return ev


def recompute_result(db: Session, sub: Submission) -> Result:
    evs = list(db.scalars(select(Evaluation).where(Evaluation.submission_id == sub.id)))
    qs = {q.id: q for q in db.scalars(select(Question).where(Question.id.in_([e.question_id for e in evs] or [-1]))
                                      .options(selectinload(Question.objective)))}
    total = sum(e.score for e in evs)
    mx = sum(e.max_score for e in evs)
    pct = percent(total, mx)
    level, _ = level_for(pct)
    items = []
    for e in sorted(evs, key=lambda e: qs[e.question_id].number):
        q = qs[e.question_id]
        label = q.objective.description if q.objective else (q.text[:60] if q.text else f"{q.number}-тапсырма")
        items.append({"label": f"{q.number}-тапсырма: {label}", "percent": percent(e.score, e.max_score),
                      "error_category": e.error_category})
    text, strengths, weaknesses = build_feedback(items, pct)
    res = db.scalar(select(Result).where(Result.submission_id == sub.id))
    if res is None:
        res = Result(submission_id=sub.id, assessment_id=sub.assessment_id)
        db.add(res)
    res.student_id = sub.student_id
    res.total_score, res.max_score, res.percent, res.level = total, mx, pct, level
    if not res.feedback_edited:
        res.feedback = text
    res.strengths, res.weaknesses = strengths, weaknesses
    if res.is_final:
        sub.status = "approved"
    elif not sub.student_id or any(e.review_status == "needs_review" for e in evs):
        sub.status = "needs_review"
    else:
        sub.status = "ready"  # only medium/high-confidence answers left: one-click approval
    return res


def job_stats(db: Session, job_id: int) -> dict:
    subs = list(db.scalars(select(Submission).where(Submission.job_id == job_id)))
    ids = [s.id for s in subs] or [-1]
    evs = list(db.scalars(select(Evaluation).where(Evaluation.submission_id.in_(ids))))
    by = {"auto_approved": 0, "medium": 0, "needs_review": 0}
    for e in evs:
        by[e.review_status] = by.get(e.review_status, 0) + 1
    return {"answers": len(evs), "by_review_status": by,
            "students_unknown": sum(1 for s in subs if not s.student_id),
            "finished_at": datetime.now(UTC).isoformat()}
