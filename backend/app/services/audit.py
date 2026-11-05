"""Audit trail helper. Every important action goes through `audit()`."""
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog, User


def audit(db: Session, user: User | None, action: str, entity_type: str | None = None,
          entity_id: Any = None, before: dict | None = None, after: dict | None = None,
          request: Request | None = None, commit: bool = False) -> AuditLog:
    log = AuditLog(
        user_id=user.id if user else None,
        school_id=user.school_id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before=before,
        after=after,
        ip=(request.client.host if request and request.client else None),
        user_agent=(request.headers.get("user-agent", "")[:255] if request else None),
    )
    db.add(log)
    if commit:
        db.commit()
    return log
