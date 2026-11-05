"""Runtime-editable settings stored in app_settings (override env defaults)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AppSetting

EDITABLE = {
    "AI_ENABLED": bool, "AI_PROVIDER": str, "AI_SEND_STUDENT_NAMES": bool, "AI_SEND_IMAGES": bool,
    "OCR_PROVIDER": str, "OCR_LANGUAGES": str, "CONFIDENCE_HIGH": float, "CONFIDENCE_MEDIUM": float,
    "AUTO_APPROVE_HIGH_CONFIDENCE": bool, "RETENTION_DAYS": int, "MAX_UPLOAD_MB": int,
}


def current(db: Session) -> dict:
    out = {k: getattr(settings, k) for k in EDITABLE}
    for row in db.scalars(select(AppSetting).where(AppSetting.key.in_(list(EDITABLE)))):
        out[row.key] = row.value
    out["providers"] = {"ai": ["local", "openai", "anthropic"], "ocr": ["tesseract", "google", "azure"]}
    out["keys_configured"] = {"openai": bool(settings.OPENAI_API_KEY), "anthropic": bool(settings.ANTHROPIC_API_KEY),
                              "google": bool(settings.GOOGLE_VISION_API_KEY), "azure": bool(settings.AZURE_VISION_KEY)}
    return out


def apply(db: Session) -> None:
    """Load persisted overrides into the process settings object (called at startup / after update)."""
    for row in db.scalars(select(AppSetting).where(AppSetting.key.in_(list(EDITABLE)))):
        try:
            setattr(settings, row.key, EDITABLE[row.key](row.value))
        except (TypeError, ValueError):
            pass


def update(db: Session, values: dict) -> dict:
    for k, v in values.items():
        if k not in EDITABLE:
            continue
        v = EDITABLE[k](v)
        row = db.scalar(select(AppSetting).where(AppSetting.key == k))
        if row:
            row.value = v
        else:
            db.add(AppSetting(key=k, value=v))
        setattr(settings, k, v)
    db.flush()
    return current(db)
