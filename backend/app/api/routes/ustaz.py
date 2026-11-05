"""Pick students in Ustaz (the school's e-journal) and import them into Planit."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import staff, teacher_of
from app.models import School, User
from app.services.audit import audit
from app.services.integrations import ustaz

router = APIRouter(prefix="/integrations/ustaz", tags=["integrations"])


class ImportIn(BaseModel):
    student_ids: list[int] = Field(min_length=1, max_length=5000)


def _school(db: Session, user: User) -> School:
    school = db.get(School, user.school_id) if user.school_id else None
    if not school:
        raise HTTPException(400, "Сіз мектепке тіркелмегенсіз")
    if not (school.idp_code or "").strip():
        raise HTTPException(400, "Мектептің iMARLEN ID коды жоқ (Баптаулар → Мектеп)")
    return school


def _roster(school: School) -> dict:
    try:
        return ustaz.fetch_roster(school.idp_code.strip())
    except ustaz.UstazError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("/status")
def status(user: User = Depends(staff)):
    return {"configured": ustaz.configured()}


@router.get("/roster")
def roster(db: Session = Depends(get_db), user: User = Depends(staff)):
    """Ustaz classes and students, each marked with what Planit already has."""
    school = _school(db, user)
    data = _roster(school)
    matched = ustaz.match_classes(db, school.id, data)
    have = ustaz.imported_refs(db, school.id)
    classes = []
    for uc in data["classes"]:
        pc = matched.get(int(uc["id"]))
        students = []
        for us in uc.get("students") or []:
            s = have.get(f"{ustaz.PREFIX}{us['id']}")
            students.append({
                "id": int(us["id"]),
                "full_name": us.get("full_name") or "",
                "gender": ustaz.gender_of(us.get("gender")),
                "imported": bool(s and s.is_active),
                "planit_class": s.school_class.name if s and s.school_class else None,
            })
        classes.append({"id": int(uc["id"]), "name": uc.get("name") or "", "grade": uc.get("grade"),
                        "letter": uc.get("letter"), "planit_class_id": pc.id if pc else None,
                        "planit_class_name": pc.name if pc else None, "students": students})
    return {"school": data.get("school"), "year": data.get("year"), "classes": classes}


@router.post("/import")
def import_students(body: ImportIn, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    school = _school(db, user)
    data = _roster(school)
    teacher = teacher_of(db, user) if user.role == "teacher" else None
    out = ustaz.import_students(db, school.id, data, set(body.student_ids), teacher)
    audit(db, user, "student.import_ustaz", "school", school.id, after=out, request=request)
    db.commit()
    return out
