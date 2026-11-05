"""Application configuration (12-factor, read from environment / .env)."""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Planit"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = False
    API_PREFIX: str = "/api"
    FRONTEND_ORIGINS: str = "http://localhost:3000"

    # Database / queue
    DATABASE_URL: str = "postgresql+psycopg2://planit:planit@localhost:5432/planit"
    REDIS_URL: str = "redis://localhost:6379/0"
    # celery: real Celery workers; thread: in-process background threads (dev / single node);
    # eager: run synchronously inside the request (tests)
    QUEUE_MODE: Literal["celery", "thread", "eager"] = "celery"

    # Security
    SECRET_KEY: str = "change-me-in-production-please-32+chars"
    ACCESS_TOKEN_MINUTES: int = 30
    REFRESH_TOKEN_DAYS: int = 7
    COOKIE_SECURE: bool = False
    COOKIE_DOMAIN: str | None = None
    RATE_LIMIT_LOGIN_PER_MIN: int = 10
    RATE_LIMIT_UPLOAD_PER_MIN: int = 30

    # Sign-in through iMARLEN ID (OIDC). All four set = the "iMARLEN ID" button appears on /login.
    IID_ISSUER: str = ""
    IID_CLIENT_ID: str = ""
    IID_CLIENT_SECRET: str = ""
    PUBLIC_URL: str = ""  # e.g. https://checker.imarlen.kz
    # create a school from the iMARLEN ID claims when no school has a matching idp_code
    IID_AUTO_CREATE_SCHOOL: bool = True

    # Storage
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    STORAGE_LOCAL_PATH: str = "./data/storage"
    STORAGE_ENCRYPTION_KEY: str = ""  # base64 32-byte key; empty = no encryption
    S3_ENDPOINT_URL: str | None = None
    S3_BUCKET: str = "planit"
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_REGION: str = "us-east-1"

    # Uploads
    MAX_UPLOAD_MB: int = 100
    MAX_FILES_PER_UPLOAD: int = 200
    CLAMAV_HOST: str | None = None
    CLAMAV_PORT: int = 3310
    PDF_DPI: int = 200

    # OCR
    OCR_PROVIDER: str = "tesseract"
    OCR_FALLBACKS: str = ""
    OCR_LANGUAGES: str = "kaz+rus+eng"
    OCR_TIMEOUT_SEC: int = 60
    GOOGLE_VISION_API_KEY: str | None = None
    AZURE_VISION_ENDPOINT: str | None = None
    AZURE_VISION_KEY: str | None = None

    # AI
    AI_ENABLED: bool = True
    AI_PROVIDER: str = "local"  # local | openai | anthropic
    AI_TIMEOUT_SEC: int = 45
    AI_SEND_STUDENT_NAMES: bool = False
    AI_SEND_IMAGES: bool = False
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-sonnet-5-5"

    # Scoring thresholds (percent)
    CONFIDENCE_HIGH: float = Field(95.0, ge=0, le=100)
    CONFIDENCE_MEDIUM: float = Field(80.0, ge=0, le=100)
    AUTO_APPROVE_HIGH_CONFIDENCE: bool = True

    # Privacy
    RETENTION_DAYS: int = 365

    # Demo
    SEED_DEMO: bool = False

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.FRONTEND_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
