"""Planit API — FastAPI application factory."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin, assessments, auth, bank, org, processing, results, review
from app.core.config import settings

logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

def on_startup() -> None:
    from app.core.db import SessionLocal
    from app.services import app_settings

    db = SessionLocal()
    try:
        app_settings.apply(db)
        if settings.QUEUE_MODE == "thread":  # in-process jobs cannot survive a restart
            from app.models import ProcessingJob

            for j in db.query(ProcessingJob).filter(ProcessingJob.status.in_(["queued", "running"])):
                j.status, j.error = "failed", "Сервер қайта іске қосылды. Файлдарды қайта жүктеңіз."
            db.commit()
    except Exception:  # table may not exist yet before migrations
        logging.getLogger("planit").warning("app_settings not loaded")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    on_startup()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Planit API",
    version="1.0.0",
    description="БЖБ / ТЖБ / АБ жұмыстарын сканерлеп автоматты тексеретін жүйенің REST API-і.",
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "camera=(self), microphone=()")
    if not request.url.path.startswith(f"{settings.API_PREFIX}/docs"):
        resp.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    if settings.COOKIE_SECURE:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resp


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logging.getLogger("planit").exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Ішкі қате. Әкімшіге хабарласыңыз."})


for r in (auth.router, org.router, assessments.router, processing.router, review.router, results.router,
          bank.router, admin.router):
    app.include_router(r, prefix=settings.API_PREFIX)
