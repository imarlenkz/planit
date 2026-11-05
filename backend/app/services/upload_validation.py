"""Upload validation: size limit, magic-byte type detection, PDF sanity, optional ClamAV malware scan."""
import socket
import struct

from app.core.config import settings

ALLOWED = {"application/pdf": (".pdf",), "image/jpeg": (".jpg", ".jpeg"), "image/png": (".png",)}


class UploadRejected(ValueError):
    pass


def sniff_mime(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return None


def clamav_scan(data: bytes) -> None:
    if not settings.CLAMAV_HOST:
        return
    try:
        with socket.create_connection((settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=30) as s:
            s.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), 1 << 16):
                chunk = data[i:i + (1 << 16)]
                s.sendall(struct.pack("!L", len(chunk)) + chunk)
            s.sendall(struct.pack("!L", 0))
            reply = s.recv(4096).decode(errors="ignore")
    except OSError as e:
        raise UploadRejected(f"Вирусқа тексеру сервисі қолжетімсіз: {e}") from e
    if "FOUND" in reply:
        raise UploadRejected("Файлда зиянды код табылды")


def validate_upload(filename: str, data: bytes) -> str:
    if not data:
        raise UploadRejected(f"{filename}: файл бос")
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise UploadRejected(f"{filename}: файл {settings.MAX_UPLOAD_MB} МБ-тан үлкен")
    mime = sniff_mime(data)
    if mime is None:
        raise UploadRejected(f"{filename}: тек JPG, PNG, PDF қабылданады")
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext and ext not in ALLOWED[mime]:
        raise UploadRejected(f"{filename}: кеңейтім мазмұнға сәйкес емес")
    if mime == "application/pdf" and b"/JavaScript" in data[:2_000_000]:
        raise UploadRejected(f"{filename}: PDF ішінде JavaScript бар — қабылданбайды")
    clamav_scan(data)
    return mime
