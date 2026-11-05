"""Ustaz (ustaz.imarlen.kz, the school's e-journal) → Planit: pick and import students.

Ustaz serves the current school year's classes and active students at
GET {USTAZ_API_URL}/integration/planit/roster?school_code=<iMARLEN ID school code>
with the X-Integration-Key header (PLANIT_INTEGRATION_KEY in Ustaz = USTAZ_INTEGRATION_KEY here).
Only names, gender and class are sent; no IIN, phones or parents.
"""
import re
import secrets

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import ClassTeacher, SchoolClass, Student, Teacher

PREFIX = "ustaz:"


class UstazError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def configured() -> bool:
    return bool(settings.USTAZ_INTEGRATION_KEY.strip())


def fetch_roster(school_code: str) -> dict:
    if not configured():
        raise UstazError(503, "Ұстазбен байланыс бапталмаған (USTAZ_INTEGRATION_KEY)")
    url = settings.USTAZ_API_URL.rstrip("/") + "/integration/planit/roster"
    try:
        r = httpx.get(url, params={"school_code": school_code}, timeout=20,
                      headers={"X-Integration-Key": settings.USTAZ_INTEGRATION_KEY.strip(), "Accept": "application/json"})
    except httpx.HTTPError as e:
        raise UstazError(502, f"Ұстаз жауап бермеді: {e.__class__.__name__}") from e
    if r.status_code == 404:
        raise UstazError(404, f"Ұстазда «{school_code}» кодты мектеп табылмады")
    if r.status_code in (401, 403):
        raise UstazError(502, "Ұстаз интеграция кілтін қабылдамады")
    if r.status_code == 503:
        raise UstazError(502, "Ұстазда PLANIT_INTEGRATION_KEY орнатылмаған")
    if r.status_code >= 400:
        raise UstazError(502, f"Ұстаз қатесі ({r.status_code})")
    try:
        data = r.json()
    except ValueError as e:
        raise UstazError(502, "Ұстаз жауабы JSON емес") from e
    if not isinstance(data, dict) or not isinstance(data.get("classes"), list):
        raise UstazError(502, "Ұстаз жауабының пішімі белгісіз")
    return data


def norm(s: str | None) -> str:
    return re.sub(r"[\s\-–—_.«»\"']+", "", (s or "")).lower().replace("ё", "е")


def gender_of(g: str | None) -> str | None:
    g = (g or "").strip().upper()
    return {"M": "m", "F": "f"}.get(g)


def academic_year_of(name: str | None) -> str | None:
    m = re.search(r"(20\d\d)\s*[-–/]\s*(20\d\d)", name or "")
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _class_key(name: str | None, grade: int | None, letter: str | None) -> str:
    return norm(name) or f"{grade}{norm(letter)}"


def match_classes(db: Session, school_id: int, roster: dict) -> dict[int, SchoolClass]:
    """Ustaz class id → existing Planit class (by external_ref, then by name / grade+letter)."""
    classes = list(db.scalars(select(SchoolClass).where(SchoolClass.school_id == school_id)))
    by_ref = {c.external_ref: c for c in classes if c.external_ref}
    by_name: dict[str, SchoolClass] = {}
    for c in classes:
        if not c.external_ref:
            by_name.setdefault(_class_key(c.name, c.grade, c.letter), c)
            by_name.setdefault(f"{c.grade}{norm(c.letter)}", c)
    out: dict[int, SchoolClass] = {}
    for uc in roster["classes"]:
        c = by_ref.get(f"{PREFIX}{uc['id']}") or by_name.get(_class_key(uc.get("name"), uc.get("grade"), uc.get("letter"))) \
            or by_name.get(f"{uc.get('grade')}{norm(uc.get('letter'))}")
        if c:
            out[int(uc["id"])] = c
    return out


def imported_refs(db: Session, school_id: int) -> dict[str, Student]:
    rows = db.scalars(select(Student).where(Student.school_id == school_id, Student.external_ref.like(f"{PREFIX}%")))
    return {s.external_ref: s for s in rows}


def import_students(db: Session, school_id: int, roster: dict, student_ids: set[int], teacher: Teacher | None) -> dict:
    """Create / update the chosen students. Classes are created when missing; a teacher gets attached to them."""
    matched = match_classes(db, school_id, roster)
    existing = imported_refs(db, school_id)
    year = academic_year_of(roster.get("year"))
    counts = {"created": 0, "updated": 0, "linked": 0, "unchanged": 0, "classes_created": 0}
    touched_classes: set[int] = set()

    for uc in roster["classes"]:
        chosen = [s for s in uc.get("students") or [] if int(s["id"]) in student_ids]
        if not chosen:
            continue
        cls = matched.get(int(uc["id"]))
        if cls is None:
            grade = int(uc.get("grade") or 0)
            letter = (uc.get("letter") or "").strip()[:5] or None
            cls = SchoolClass(school_id=school_id, name=(uc.get("name") or f"{grade}{letter or ''}").strip()[:20],
                              grade=grade, letter=letter, external_ref=f"{PREFIX}{uc['id']}",
                              **({"academic_year": year} if year else {}))
            if teacher:
                cls.homeroom_teacher_id = teacher.id
            db.add(cls)
            db.flush()
            matched[int(uc["id"])] = cls
            counts["classes_created"] += 1
        elif not cls.external_ref:
            cls.external_ref = f"{PREFIX}{uc['id']}"
        touched_classes.add(cls.id)

        # students already in this Planit class without a link, to avoid duplicating hand-made rosters
        loose = {norm(s.full_name): s for s in db.scalars(
            select(Student).where(Student.class_id == cls.id, Student.external_ref.is_(None)))}

        for us in chosen:
            ref = f"{PREFIX}{us['id']}"
            name = (us.get("full_name") or "").strip()[:255]
            if len(name) < 2:
                continue
            gender = gender_of(us.get("gender"))
            s = existing.get(ref)
            if s is None and (s := loose.pop(norm(name), None)) is not None:
                s.external_ref = ref
                s.full_name, s.class_id, s.is_active = name, cls.id, True
                s.gender = gender or s.gender
                existing[ref] = s
                counts["linked"] += 1
                continue
            if s is None:
                s = Student(school_id=school_id, class_id=cls.id, full_name=name, gender=gender, external_ref=ref,
                            student_code=f"S{secrets.token_hex(4).upper()}")
                db.add(s)
                existing[ref] = s
                counts["created"] += 1
                continue
            changed = (s.full_name, s.class_id, s.is_active, s.gender) != (name, cls.id, True, gender or s.gender)
            s.full_name, s.class_id, s.is_active = name, cls.id, True
            s.gender = gender or s.gender
            counts["updated" if changed else "unchanged"] += 1

    if teacher:
        have = set(db.scalars(select(ClassTeacher.class_id).where(ClassTeacher.teacher_id == teacher.id,
                                                                  ClassTeacher.class_id.in_(touched_classes or {-1}))))
        for cid in touched_classes - have:
            db.add(ClassTeacher(class_id=cid, teacher_id=teacher.id))
    db.flush()
    counts["classes"] = len(touched_classes)
    return counts
