"""Results, analytics and exports."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import (
    assessment_query_filter,
    check_class_access,
    check_student_access,
    get_assessment_or_404,
    get_current_user,
    staff,
)
from app.models import Result, School, Student, Submission, User
from app.services import analytics as an
from app.services.audit import audit
from app.services.export import docx_report, excel_report, pdf_report

router = APIRouter(tags=["results"])


@router.get("/analytics/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(staff)):
    return an.dashboard(db, assessment_query_filter(db, user))


@router.get("/analytics/assessments/{assessment_id}")
def assessment_analytics(assessment_id: int, final_only: bool = False, db: Session = Depends(get_db),
                         user: User = Depends(staff)):
    get_assessment_or_404(db, user, assessment_id)
    return an.assessment_analytics(db, assessment_id, final_only)


@router.get("/analytics/classes/{class_id}/dynamics")
def class_dynamics(class_id: int, subject_id: int | None = None, db: Session = Depends(get_db),
                   user: User = Depends(staff)):
    check_class_access(db, user, class_id)
    return an.class_dynamics(db, class_id, subject_id)


@router.get("/assessments/{assessment_id}/results")
def assessment_results(assessment_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    get_assessment_or_404(db, user, assessment_id)
    data = an.assessment_analytics(db, assessment_id)
    return {"assessment": data["assessment"], "questions": data["questions"], "students": data["students"],
            "summary": data["summary"]}


@router.get("/students/{student_id}/results")
def student_results(student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.get(Student, student_id)
    if not s:
        raise HTTPException(404)
    check_student_access(db, user, s)
    rows = an.student_history(db, s.id)
    if user.role == "student":
        rows = [r for r in rows if r["is_final"]]
    return {"student": {"id": s.id, "full_name": s.full_name, "class_name": s.school_class.name if s.school_class else None},
            "results": rows}


@router.get("/me/results")
def my_results(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.scalar(select(Student).where(Student.user_id == user.id))
    if not s:
        raise HTTPException(404, "Оқушы профилі табылмады")
    return student_results(s.id, db, user)


@router.get("/results/{result_id}")
def get_result(result_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = db.get(Result, result_id)
    if not r:
        raise HTTPException(404)
    sub = db.get(Submission, r.submission_id)
    from app.api.routes.processing import get_submission

    return get_submission(sub.id, db, user)


def _meta(db: Session, a_id: int) -> tuple[dict, str, str]:
    data = an.assessment_analytics(db, a_id)
    from app.models import Assessment

    a = db.get(Assessment, a_id)
    school = db.get(School, a.school_id)
    teacher = a.teacher.user.full_name if a.teacher and a.teacher.user else ""
    return data, school.name if school else "", teacher


@router.get("/exports/assessments/{assessment_id}.xlsx")
def export_excel(assessment_id: int, request: Request, kind: str = Query("full", pattern="^(full|gradebook)$"),
                 db: Session = Depends(get_db), user: User = Depends(staff)):
    get_assessment_or_404(db, user, assessment_id)
    data, school, teacher = _meta(db, assessment_id)
    audit(db, user, "export.excel", "assessment", assessment_id, request=request, commit=True)
    return Response(excel_report(data, school, teacher, kind),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="planit-{assessment_id}.xlsx"'})


@router.get("/exports/assessments/{assessment_id}.pdf")
def export_pdf(assessment_id: int, request: Request, inline: bool = False, db: Session = Depends(get_db),
               user: User = Depends(staff)):
    get_assessment_or_404(db, user, assessment_id)
    data, school, teacher = _meta(db, assessment_id)
    audit(db, user, "export.pdf", "assessment", assessment_id, request=request, commit=True)
    disp = "inline" if inline else "attachment"
    return Response(pdf_report(data, school, teacher), media_type="application/pdf",
                    headers={"Content-Disposition": f'{disp}; filename="planit-{assessment_id}.pdf"'})


@router.get("/exports/assessments/{assessment_id}.docx")
def export_docx(assessment_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    get_assessment_or_404(db, user, assessment_id)
    data, school, teacher = _meta(db, assessment_id)
    audit(db, user, "export.docx", "assessment", assessment_id, request=request, commit=True)
    return Response(docx_report(data, school, teacher),
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="planit-{assessment_id}.docx"'})
