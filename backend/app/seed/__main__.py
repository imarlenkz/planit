"""`python -m app.seed [--run-demo]` — seed the demo school; optionally push the demo scan through the real pipeline.
`python -m app.seed purge` — delete the demo school, its data and the demo accounts.
`python -m app.seed create-admin EMAIL [PASSWORD]` — create the first administrator (no-op when one exists).

--run-demo (or DEMO_AUTORUN=true) generates the phone-photo-like demo PDF for the main Math БЖБ and processes it
synchronously, so a fresh deployment opens with real OCR + AI results ready for review.
"""
import os
import sys

from sqlalchemy import select

from app.core.db import SessionLocal
from app.seed import DEMO_PASSWORD, seed_demo


def run_demo(db, assessment_id: int) -> None:
    from app.api.routes.admin import _demo_pdf
    from app.models import Assessment, ProcessingJob, User
    from app.services import storage
    from app.services.pipeline import job_stats, run_job

    if db.scalar(select(ProcessingJob).where(ProcessingJob.assessment_id == assessment_id)):
        print("Demo job already exists; skipping autorun")
        return
    teacher = db.scalar(select(User).where(User.email == "teacher@planit.kz"))
    a = db.get(Assessment, assessment_id)
    pdf = _demo_pdf(db, assessment_id, teacher)
    f = storage.save_bytes(db, pdf, "application/pdf", "upload", original_name=f"demo-scan-{a.id}.pdf",
                           uploaded_by=teacher.id, school_id=a.school_id)
    job = ProcessingJob(assessment_id=a.id, created_by=teacher.id, file_ids=[f.id], status="queued", stage="uploading")
    db.add(job)
    db.commit()
    print(f"Processing demo scan (job {job.id})…", flush=True)
    run_job(job.id)
    db.expire_all()
    print("Demo job:", job_stats(db, job.id))


if __name__ == "__main__":
    db = SessionLocal()
    try:
        if sys.argv[1:2] == ["purge"]:
            from app.seed.purge import purge_demo
            print("Demo data removed:", purge_demo(db))
            sys.exit(0)
        if sys.argv[1:2] == ["create-admin"]:
            from app.seed.purge import create_admin
            if len(sys.argv) < 3:
                sys.exit("usage: python -m app.seed create-admin EMAIL [PASSWORD]")
            pw = create_admin(db, sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
            print(f"Administrator created: {sys.argv[2]} / {pw}" if pw else "An administrator already exists; nothing created")
            sys.exit(0)
        out = seed_demo(db)
        print("Demo data:", out)
        print(f"Logins (password {DEMO_PASSWORD}): teacher@planit.kz, director@planit.kz, admin@planit.kz, student@planit.kz")
        if "--run-demo" in sys.argv or os.getenv("DEMO_AUTORUN", "").lower() in ("1", "true", "yes"):
            from app.models import Assessment
            main = out.get("main_assessment_id") or db.scalar(
                select(Assessment.id).where(Assessment.title.like("Математика БЖБ №2%")).order_by(Assessment.id))
            if main:
                run_demo(db, main)
    finally:
        db.close()
