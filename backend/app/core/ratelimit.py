"""Fixed-window rate limiter backed by Redis with in-memory fallback."""
import threading
import time

from fastapi import HTTPException, Request

from app.core.config import settings

_mem: dict[str, tuple[int, float]] = {}
_lock = threading.Lock()
_redis = None


def _client():
    global _redis
    if _redis is None and settings.QUEUE_MODE != "eager":
        try:
            import redis

            _redis = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=0.5)
            _redis.ping()
        except Exception:
            _redis = False
    return _redis or None


def hit(key: str, limit: int, window: int = 60) -> bool:
    """Return True if request allowed."""
    r = _client()
    bucket = f"rl:{key}:{int(time.time() // window)}"
    if r is not None:
        try:
            n = r.incr(bucket)
            if n == 1:
                r.expire(bucket, window)
            return n <= limit
        except Exception:
            pass
    with _lock:
        count, start = _mem.get(bucket, (0, time.time()))
        _mem[bucket] = (count + 1, start)
        if len(_mem) > 10000:
            _mem.clear()
        return count + 1 <= limit


def rate_limit(name: str, limit: int):
    def dep(request: Request):
        ip = request.client.host if request.client else "unknown"
        if not hit(f"{name}:{ip}", limit):
            raise HTTPException(status_code=429, detail="Тым көп сұраныс. Біраздан соң қайталаңыз.")

    return dep
