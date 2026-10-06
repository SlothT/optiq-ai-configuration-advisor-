"""Shared production limits using the existing queue Redis; local limits for development."""
from __future__ import annotations

import hashlib
import threading
import time

from fastapi import HTTPException, Request
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings

_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {count, redis.call('TTL', KEYS[1])}
"""
_local: dict[str, tuple[int, float]] = {}
_lock = threading.Lock()


def _increment(key: str, window: int) -> tuple[int, int]:
    if settings.app_env == "production":
        try:
            with Redis.from_url(settings.redis_url, socket_connect_timeout=3, socket_timeout=3) as client:
                count, ttl = client.eval(_SCRIPT, 1, key, window)
            return int(count), max(1, int(ttl))
        except RedisError as exc:
            raise HTTPException(status_code=503, detail="Please try again shortly.") from exc
    with _lock:
        now = time.monotonic()
        for expired in [name for name, (_, until) in _local.items() if until <= now]:
            del _local[expired]
        count, until = _local.get(key, (0, now + window))
        _local[key] = (count + 1, until)
        return count + 1, max(1, int(until - now))


def check_rate_limit(request: Request, identifier: str = "", *, limit: int = 10, window: int = 300) -> None:
    # Trust only the ASGI client address, never arbitrary forwarded headers.
    ip = request.client.host if request.client else "unknown"
    subjects = [("ip:" + ip, 120)]
    if identifier:
        subjects.append(("account:" + identifier.strip().lower(), limit))
    else:
        subjects = [("ip:" + ip, limit)]
    for subject, maximum in subjects:
        digest = hashlib.sha256(subject.encode()).hexdigest()
        count, retry_after = _increment(f"optiq:limit:{request.url.path}:{digest}", window)
        if count > maximum:
            raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.", headers={"Retry-After": str(retry_after)})
