"""Storage abstraction: local filesystem or S3-compatible object storage, with encryption at rest."""
import hashlib
import os
import uuid
from pathlib import Path
from typing import Protocol

from app.core import crypto
from app.core.config import settings


class StorageBackend(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError("invalid key")
        return p

    def put(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, p)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            pass


class S3Storage:
    def __init__(self):
        import boto3

        self.bucket = settings.S3_BUCKET
        self.client = boto3.client(
            "s3", endpoint_url=settings.S3_ENDPOINT_URL, aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY, region_name=settings.S3_REGION,
        )
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            try:
                self.client.create_bucket(Bucket=self.bucket)
            except Exception:
                pass

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ServerSideEncryption="AES256")

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


_backend: StorageBackend | None = None


def backend() -> StorageBackend:
    global _backend
    if _backend is None:
        _backend = S3Storage() if settings.STORAGE_BACKEND == "s3" else LocalStorage(settings.STORAGE_LOCAL_PATH)
    return _backend


def save_bytes(db, data: bytes, mime: str, kind: str, original_name: str | None = None,
               uploaded_by: int | None = None, school_id: int | None = None):
    from app.models import File

    ext = {"image/png": ".png", "image/jpeg": ".jpg", "application/pdf": ".pdf",
           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx"}.get(mime, ".bin")
    key = f"{kind}/{uuid.uuid4().hex[:2]}/{uuid.uuid4().hex}{ext}"
    backend().put(key, crypto.encrypt(data))
    f = File(storage_key=key, original_name=original_name, mime=mime, size=len(data),
             sha256=hashlib.sha256(data).hexdigest(), encrypted=crypto.encryption_enabled(), kind=kind,
             uploaded_by=uploaded_by, school_id=school_id)
    db.add(f)
    db.flush()
    return f


def read_file(f) -> bytes:
    return crypto.decrypt(backend().get(f.storage_key))


def delete_file(db, f) -> None:
    backend().delete(f.storage_key)
    db.delete(f)
