from celery import Celery

from app.core.config import settings

celery_app = Celery("planit", broker=settings.REDIS_URL, backend=settings.REDIS_URL, include=["app.workers.tasks"])
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=60 * 60,
    task_soft_time_limit=55 * 60,
    task_default_queue="planit",
    broker_connection_retry_on_startup=True,
    beat_schedule={"purge-old-files": {"task": "app.workers.tasks.purge_expired_files", "schedule": 24 * 3600}},
)
