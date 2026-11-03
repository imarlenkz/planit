"""Audit log and application settings."""
from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import PK, IdMixin, TimestampMixin


class AuditLog(IdMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"
    user_id: Mapped[int | None] = mapped_column(PK, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    school_id: Mapped[int | None] = mapped_column(PK, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(40))
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))


class AppSetting(IdMixin, TimestampMixin, Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(64), unique=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
