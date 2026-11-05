"""Remove the demo school and demo accounts from a database, and create the first real administrator."""
import secrets

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Assessment, File, School, User
from app.seed import demo_data as D
from app.services import storage

DEMO_EMAILS = ("admin@planit.kz", "director@planit.kz", "teacher@planit.kz", "teacher2@planit.kz", "student@planit.kz")


def purge_demo(db: Session) -> dict:
    if db.bind.dialect.name == "sqlite":
        db.execute(text("PRAGMA foreign_keys=ON"))
    out = {"schools": 0, "assessments": 0, "files": 0, "users": 0}
    for school in db.scalars(select(School).where(School.name == D.SCHOOL["name"])).all():
        for f in db.scalars(select(File).where(File.school_id == school.id)).all():
            try:
                storage.backend().delete(f.storage_key)
            except Exception:  # noqa: BLE001 -- a missing blob must not stop the clean-up
                pass
            out["files"] += 1
        out["assessments"] += db.execute(delete(Assessment).where(Assessment.school_id == school.id)).rowcount or 0
        db.execute(delete(File).where(File.school_id == school.id))
        db.execute(delete(School).where(School.id == school.id))
        out["schools"] += 1
    out["users"] = db.execute(delete(User).where(User.email.in_(DEMO_EMAILS))).rowcount or 0
    db.commit()
    return out


def create_admin(db: Session, email: str, password: str | None = None) -> str | None:
    """Create a platform administrator unless one already exists. Returns the password when one was created."""
    if db.scalar(select(User.id).where(User.role == "admin", User.is_active.is_(True))):
        return None
    password = password or secrets.token_urlsafe(12)
    db.add(User(email=email.lower().strip(), full_name="Әкімші", role="admin", school_id=None,
                password_hash=hash_password(password), locale="kk", is_active=True))
    db.commit()
    return password
