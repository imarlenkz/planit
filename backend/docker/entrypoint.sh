#!/bin/sh
# Planit container entrypoint: api | worker | beat | migrate | seed | <any command>
set -e

wait_for_db() {
  python - <<'PY'
import sys, time
from sqlalchemy import create_engine, text
from app.core.config import settings
for i in range(60):
    try:
        with create_engine(settings.DATABASE_URL).connect() as c:
            c.execute(text("select 1"))
        sys.exit(0)
    except Exception as e:  # noqa: BLE001
        print(f"waiting for database… ({e.__class__.__name__})", flush=True)
        time.sleep(2)
sys.exit("database is not reachable")
PY
}

case "$1" in
  api)
    wait_for_db
    alembic upgrade head
    if [ "${SEED_DEMO:-false}" = "true" ]; then
      # seeds the demo school; with DEMO_AUTORUN=true also pushes the demo scan through OCR + AI (≈1 min, once)
      python -m app.seed
    fi
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' \
      --workers "${API_WORKERS:-2}"
    ;;
  worker)
    wait_for_db
    exec celery -A app.workers.celery_app worker --loglevel "${LOG_LEVEL:-info}" --concurrency "${WORKER_CONCURRENCY:-2}"
    ;;
  beat)
    exec celery -A app.workers.celery_app beat --loglevel "${LOG_LEVEL:-info}" --schedule /tmp/celerybeat-schedule
    ;;
  migrate)
    wait_for_db
    exec alembic upgrade head
    ;;
  seed)
    wait_for_db
    shift
    exec python -m app.seed "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
