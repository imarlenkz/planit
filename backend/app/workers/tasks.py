from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.process_job", bind=True, max_retries=2)
def process_job(self, job_id: int) -> None:
    from app.services.pipeline import run_job

    run_job(job_id)


@celery_app.task(name="app.workers.tasks.purge_expired_files")
def purge_expired_files() -> int:
    """Privacy: remove raw uploads older than RETENTION_DAYS (processed page images stay for review)."""
    from app.models import File
    from app.services import storage

    cutoff = datetime.now(UTC) - timedelta(days=settings.RETENTION_DAYS)
    db = SessionLocal()
    n = 0
    try:
        for f in db.scalars(select(File).where(File.kind == "upload", File.created_at < cutoff)):
            storage.delete_file(db, f)
            n += 1
        db.commit()
    finally:
        db.close()
    return n
