"""Pick students in Ustaz (the school's e-journal) and import them into Planit."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import staff, teacher_of
from app.models import School, User
from app.services.audit import audit
from app.services.integrations import ustaz

router = APIRouter(prefix="/integrations/ustaz", tags=["integrations"])


class ImportIn(BaseModel):
    student_ids: list[int] = Field(min_length=1, max_length=5000)
    # platform admins only: which school (iMARLEN ID code) to import from / into
    school_code: str | None = Field(default=None, max_length=64)


def _school(db: Session, user: User, code: str | None) -> tuple[School | None, str]:
    """(Planit school or None if it does not exist yet, iMARLEN ID school code).

    School staff always use their own school. A platform admin (iMARLEN ID platform_owner) belongs to no school:
    they pass a code, or get their own / the only school that has a code. A school that exists in Ustaz but not
    in Planit yet is created on import.
    """
    code = (code or "").strip()
    if user.role != "admin":
        school = db.get(School, user.school_id) if user.school_id else None
        if not school:
            raise HTTPException(400, "Сіз мектепке тіркелмегенсіз")
        if not (school.idp_code or "").strip():
            raise HTTPException(400, "Мектептің iMARLEN ID коды жоқ (Баптаулар → Мектеп)")
        return school, school.idp_code.strip()
    if code:
        school = db.scalar(select(School).where(func.lower(School.idp_code) == code.lower()))
        return school, (school.idp_code.strip() if school else code)
    if user.school_id and (s := db.get(School, user.school_id)) and (s.idp_code or "").strip():
        return s, s.idp_code.strip()
    coded = list(db.scalars(select(School).where(School.idp_code.is_not(None), School.idp_code != "")))
    if len(coded) == 1:
        return coded[0], coded[0].idp_code.strip()
    raise HTTPException(400, "Мектептің iMARLEN ID кодын енгізіңіз")


def _roster(code: str) -> dict:
    try:
        return ustaz.fetch_roster(code)
    except ustaz.UstazError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("/status")
def status(db: Session = Depends(get_db), user: User = Depends(staff)):
    out: dict = {"configured": ustaz.configured()}
    if user.role == "admin":
        out["schools"] = [{"id": s.id, "name": s.name, "idp_code": s.idp_code} for s in db.scalars(
            select(School).where(School.idp_code.is_not(None), School.idp_code != "").order_by(School.name))]
    return out


@router.get("/roster")
def roster(school_code: str | None = None, db: Session = Depends(get_db), user: User = Depends(staff)):
    """Ustaz classes and students, each marked with what Planit already has."""
    school, code = _school(db, user, school_code)
    data = _roster(code)
    matched = ustaz.match_classes(db, school.id, data) if school else {}
    have = ustaz.imported_refs(db, school.id) if school else {}
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
    return {"school": data.get("school"), "school_code": code, "planit_school_id": school.id if school else None,
            "year": data.get("year"), "classes": classes}


@router.post("/import")
def import_students(body: ImportIn, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    school, code = _school(db, user, body.school_code)
    data = _roster(code)
    if school is None:  # admin importing a school that Planit does not have yet
        name = ((data.get("school") or {}).get("name") or code).strip()[:255]
        school = School(name=name, idp_code=code)
        db.add(school)
        db.flush()
    teacher = teacher_of(db, user) if user.role == "teacher" else None
    out = ustaz.import_students(db, school.id, data, set(body.student_ids), teacher)
    audit(db, user, "student.import_ustaz", "school", school.id, after={**out, "school_code": code}, request=request)
    db.commit()
    return out
