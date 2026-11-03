"""Dispatch processing jobs: Celery workers in production, threads in single-node dev, eager in tests."""
import threading

from app.core.config import settings


def enqueue_job(job_id: int) -> None:
    mode = settings.QUEUE_MODE
    if mode == "celery":
        from app.workers.tasks import process_job

        process_job.delay(job_id)
    elif mode == "thread":
        from app.services.pipeline import run_job

        threading.Thread(target=run_job, args=(job_id,), daemon=True, name=f"job-{job_id}").start()
    else:
        from app.services.pipeline import run_job

        run_job(job_id)
