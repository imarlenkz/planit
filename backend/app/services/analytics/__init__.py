"""Analytics: class/assessment summaries, task & descriptor difficulty, learning objectives, error clustering,
gender split, dynamics, AI-style insights (deterministic text built from the numbers)."""
from collections import Counter, defaultdict
from datetime import UTC, datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Analytics,
    Assessment,
    Evaluation,
    ProcessingJob,
    Question,
    Result,
    Student,
    Submission,
)
from app.services.scoring import level_for, percent

ERROR_LABELS = {
    "calculation": "Есептеу қатесі", "formula": "Формуланы қате қолдану", "concept": "Ұғымды түсінбеу",
    "terminology": "Термин қатесі", "spelling": "Орфографиялық қате", "logic": "Логикалық қате",
    "task_misunderstanding": "Тапсырманы түсінбеу", "incomplete": "Толық емес жауап",
}
LEVEL_LABELS = {"high": "Жоғары", "medium": "Орташа", "low": "Төмен", "very_low": "Өте төмен"}


def _avg(xs):
    xs = list(xs)
    return round(sum(xs) / len(xs), 1) if xs else 0.0


def assessment_analytics(db: Session, assessment_id: int, final_only: bool = False) -> dict:
    a = db.get(Assessment, assessment_id)
    subs = list(db.scalars(select(Submission).where(Submission.assessment_id == a.id, Submission.student_id.is_not(None))
                           .options(selectinload(Submission.student))))
    sub_ids = [s.id for s in subs] or [-1]
    results = {r.submission_id: r for r in db.scalars(select(Result).where(Result.submission_id.in_(sub_ids)))}
    if final_only:
        subs = [s for s in subs if results.get(s.id) and results[s.id].is_final]
    version_ids = [v.id for v in a.versions]
    questions = list(db.scalars(select(Question).where(Question.version_id.in_(version_ids or [-1]))
                                .options(selectinload(Question.descriptors), selectinload(Question.objective))
                                .order_by(Question.number)))
    qmap = {q.id: q for q in questions}
    evs = list(db.scalars(select(Evaluation).where(Evaluation.submission_id.in_(sub_ids))
                          .options(selectinload(Evaluation.items))))
    by_sub = defaultdict(dict)
    for e in evs:
        by_sub[e.submission_id][e.question_id] = e

    roster = db.scalar(select(func.count()).where(Student.class_id == a.class_id, Student.is_active.is_(True))) or 0
    pcts = [results[s.id].percent for s in subs if s.id in results]
    marks = Counter(level_for(p)[1] for p in pcts)
    levels = Counter(level_for(p)[0] for p in pcts)
    summary = {
        "students_total": roster, "submitted": len(subs),
        "avg_score": _avg(results[s.id].total_score for s in subs if s.id in results),
        "max_score": a.max_score, "avg_percent": _avg(pcts),
        "max_percent": max(pcts) if pcts else 0, "min_percent": min(pcts) if pcts else 0,
        "success_rate": round(sum(1 for p in pcts if p >= 40) / len(pcts) * 100, 1) if pcts else 0,  # үлгерім
        "quality_rate": round(sum(1 for p in pcts if p >= 65) / len(pcts) * 100, 1) if pcts else 0,  # білім сапасы
        "marks": {str(k): marks.get(k, 0) for k in (5, 4, 3, 2)},
        "levels": {k: levels.get(k, 0) for k in LEVEL_LABELS},
    }

    q_stats = []
    for q in questions:
        es = [by_sub[s.id][q.id] for s in subs if q.id in by_sub[s.id]]
        avg = _avg(e.score for e in es)
        q_stats.append({"question_id": q.id, "number": q.number, "max_score": q.max_score, "avg_score": avg,
                        "percent": percent(sum(e.score for e in es), q.max_score * len(es)) if es else 0,
                        "correct": sum(1 for e in es if e.status == "correct"),
                        "partial": sum(1 for e in es if e.status == "partial"),
                        "incorrect": sum(1 for e in es if e.status == "incorrect"),
                        "objective": q.objective.code if q.objective else None, "answer_type": q.answer_type})
    hardest = min(q_stats, key=lambda x: x["percent"]) if q_stats and subs else None

    d_stats = []
    for q in questions:
        for d in q.descriptors:
            items = [it for s in subs for e in [by_sub[s.id].get(q.id)] if e for it in e.items if it.descriptor_id == d.id]
            if not items:
                continue
            d_stats.append({"question_number": q.number, "number": d.number, "text": d.text,
                            "label": f"{q.number}.{d.number}",
                            "percent": round(sum(1 for it in items if it.met) / len(items) * 100, 1)})
    weakest_d = min(d_stats, key=lambda x: x["percent"]) if d_stats else None

    obj_acc: dict[str, list] = defaultdict(lambda: [0.0, 0.0, ""])
    for q in questions:
        if not q.objective:
            continue
        for s in subs:
            e = by_sub[s.id].get(q.id)
            if e:
                acc = obj_acc[q.objective.code]
                acc[0] += e.score
                acc[1] += e.max_score
                acc[2] = q.objective.description
    o_stats = sorted([{"code": k, "description": v[2], "percent": percent(v[0], v[1])} for k, v in obj_acc.items()],
                     key=lambda x: x["code"])

    errors = Counter(e.error_category for e in evs if e.error_category and e.status != "correct"
                     and e.submission_id in {s.id for s in subs})
    error_list = [{"category": k, "label": ERROR_LABELS.get(k, k), "count": v} for k, v in errors.most_common()]

    gender = {}
    for g in ("m", "f"):
        gp = [results[s.id].percent for s in subs if s.id in results and s.student and s.student.gender == g]
        gender[g] = {"count": len(gp), "avg_percent": _avg(gp)}

    hist = [0] * 10
    for p in pcts:
        hist[min(9, int(p // 10))] += 1
    histogram = [{"range": f"{i * 10}–{i * 10 + 10}", "count": c} for i, c in enumerate(hist)]

    students = []
    heatmap = []
    for s in sorted(subs, key=lambda s: s.student.full_name):
        r = results.get(s.id)
        if not r:
            continue
        lvl, mark = level_for(r.percent)
        students.append({"submission_id": s.id, "student_id": s.student_id, "name": s.student.full_name,
                         "gender": s.student.gender, "total": r.total_score, "max": r.max_score, "percent": r.percent,
                         "level": lvl, "mark": mark, "is_final": r.is_final,
                         "scores": {qmap[qid].number: e.score for qid, e in by_sub[s.id].items() if qid in qmap}})
        heatmap.append({"name": s.student.full_name,
                        "cells": [percent(by_sub[s.id][q.id].score, q.max_score) if q.id in by_sub[s.id] else None
                                  for q in questions]})

    insights = []
    if hardest:
        insights.append(f"{hardest['number']}-тапсырма сынып үшін ең қиын тапсырма болды ({hardest['percent']}%).")
    if weakest_d and weakest_d["percent"] < 70:
        insights.append(f"Оқушылардың көпшілігі {weakest_d['question_number']}-тапсырманың {weakest_d['number']}-дескрипторы "
                        f"бойынша қиналған: «{weakest_d['text']}» ({weakest_d['percent']}%).")
    weak_obj = min(o_stats, key=lambda x: x["percent"]) if o_stats else None
    if weak_obj and weak_obj["percent"] < 70:
        insights.append(f"Назар аудару керек оқу мақсаты: {weak_obj['code']} — {weak_obj['description']} ({weak_obj['percent']}%).")
    if error_list:
        insights.append(f"Ең жиі қате түрі: {error_list[0]['label'].lower()} ({error_list[0]['count']} жағдай).")
    if gender["m"]["count"] and gender["f"]["count"]:
        diff = gender["f"]["avg_percent"] - gender["m"]["avg_percent"]
        if abs(diff) >= 7:
            insights.append(f"{'Қыздардың' if diff > 0 else 'Ұлдардың'} орташа нәтижесі {abs(diff):.0f}%-ға жоғары.")
    main_problem = (weak_obj["description"] if weak_obj and weak_obj["percent"] < 70
                    else (weakest_d["text"] if weakest_d else None))

    payload = {"assessment": {"id": a.id, "title": a.title, "type": a.type, "class_id": a.class_id,
                              "class_name": a.school_class.name, "subject": a.subject.name,
                              "date": a.date.isoformat() if a.date else None, "max_score": a.max_score},
               "summary": summary, "questions": q_stats, "hardest_question": hardest, "descriptors": d_stats,
               "objectives": o_stats, "errors": error_list, "gender": gender, "histogram": histogram,
               "students": students, "heatmap": {"questions": [q.number for q in questions], "rows": heatmap},
               "insights": insights, "main_problem": main_problem}
    _cache(db, a, payload)
    return payload


def _cache(db: Session, a: Assessment, payload: dict) -> None:
    row = db.scalar(select(Analytics).where(Analytics.assessment_id == a.id, Analytics.kind == "assessment_summary"))
    if row is None:
        row = Analytics(assessment_id=a.id, class_id=a.class_id, kind="assessment_summary")
        db.add(row)
    row.payload = {"summary": payload["summary"], "insights": payload["insights"]}
    row.computed_at = datetime.now(UTC)
    db.commit()


def dashboard(db: Session, assessment_filter) -> dict:
    a_ids = list(db.scalars(select(Assessment.id).where(assessment_filter)))
    ids = a_ids or [-1]
    today = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
    checked_today = db.scalar(select(func.count()).select_from(Submission).where(
        Submission.assessment_id.in_(ids), Submission.created_at >= today)) or 0
    in_progress = db.scalar(select(func.count()).select_from(ProcessingJob).where(
        ProcessingJob.assessment_id.in_(ids), ProcessingJob.status.in_(["queued", "running"]))) or 0
    needs_review = db.scalar(select(func.count()).select_from(Evaluation).join(Submission, Submission.id == Evaluation.submission_id)
                             .where(Submission.assessment_id.in_(ids), Evaluation.review_status == "needs_review")) or 0
    unknown = db.scalar(select(func.count()).select_from(Submission).where(
        Submission.assessment_id.in_(ids), Submission.student_id.is_(None))) or 0
    completed = db.scalar(select(func.count()).select_from(Submission).where(
        Submission.assessment_id.in_(ids), Submission.status == "approved")) or 0
    total_subs = db.scalar(select(func.count()).select_from(Submission).where(Submission.assessment_id.in_(ids))) or 0
    recent = []
    for a in db.scalars(select(Assessment).where(Assessment.id.in_(ids)).order_by(Assessment.date.desc().nullslast(),
                                                                                  Assessment.id.desc()).limit(6)):
        avg = db.scalar(select(func.avg(Result.percent)).where(Result.assessment_id == a.id))
        recent.append({"id": a.id, "title": a.title, "type": a.type, "class_name": a.school_class.name,
                       "subject": a.subject.name, "status": a.status, "date": a.date.isoformat() if a.date else None,
                       "avg_percent": round(avg, 1) if avg is not None else None})
    by_type = dict(db.execute(select(Assessment.type, func.count()).where(Assessment.id.in_(ids))
                              .group_by(Assessment.type)).all())
    review_split = dict(db.execute(select(Evaluation.review_status, func.count()).join(
        Submission, Submission.id == Evaluation.submission_id).where(Submission.assessment_id.in_(ids))
        .group_by(Evaluation.review_status)).all())
    return {"cards": {"checked_today": checked_today, "in_progress": in_progress, "needs_review": needs_review,
                      "unknown_students": unknown, "completed": completed, "total_submissions": total_subs,
                      "assessments": len(a_ids)},
            "recent": recent, "by_type": by_type, "review_split": review_split}


def class_dynamics(db: Session, class_id: int, subject_id: int | None = None) -> list[dict]:
    stmt = select(Assessment).where(Assessment.class_id == class_id)
    if subject_id:
        stmt = stmt.where(Assessment.subject_id == subject_id)
    out = []
    for a in db.scalars(stmt.order_by(Assessment.date.asc().nullslast())):
        avg = db.scalar(select(func.avg(Result.percent)).where(Result.assessment_id == a.id))
        if avg is None:
            continue
        out.append({"assessment_id": a.id, "title": a.title, "type": a.type, "subject": a.subject.name,
                    "date": a.date.isoformat() if a.date else None, "avg_percent": round(avg, 1)})
    return out


def student_history(db: Session, student_id: int) -> list[dict]:
    rows = db.execute(select(Result, Assessment).join(Assessment, Assessment.id == Result.assessment_id)
                      .where(Result.student_id == student_id).order_by(Assessment.date.asc().nullslast()))
    return [{"result_id": r.id, "submission_id": r.submission_id, "assessment_id": a.id, "title": a.title,
             "type": a.type, "subject": a.subject.name, "date": a.date.isoformat() if a.date else None,
             "total": r.total_score, "max": r.max_score, "percent": r.percent, "level": r.level, "is_final": r.is_final}
            for r, a in rows]


