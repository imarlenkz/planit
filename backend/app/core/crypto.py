"""AES-256-GCM encryption for stored files (encryption at rest)."""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

MAGIC = b"PLNT1"


def _key() -> bytes | None:
    if not settings.STORAGE_ENCRYPTION_KEY:
        return None
    key = base64.b64decode(settings.STORAGE_ENCRYPTION_KEY)
    if len(key) != 32:
        raise ValueError("STORAGE_ENCRYPTION_KEY must be base64 of 32 bytes")
    return key


def encryption_enabled() -> bool:
    return _key() is not None


def encrypt(data: bytes) -> bytes:
    key = _key()
    if key is None:
        return data
    nonce = os.urandom(12)
    return MAGIC + nonce + AESGCM(key).encrypt(nonce, data, None)


def decrypt(data: bytes) -> bytes:
    if not data.startswith(MAGIC):
        return data
    key = _key()
    if key is None:
        raise ValueError("Encrypted file but STORAGE_ENCRYPTION_KEY is not set")
    nonce, body = data[len(MAGIC):len(MAGIC) + 12], data[len(MAGIC) + 12:]
    return AESGCM(key).decrypt(nonce, body, None)
