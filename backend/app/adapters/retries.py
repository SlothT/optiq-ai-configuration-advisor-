from __future__ import annotations

import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TypeVar

import httpx

logger = logging.getLogger("optiq.adapters")

T = TypeVar("T")
_attempt_limit: ContextVar[int | None] = ContextVar("optiq_attempt_limit", default=None)


@contextmanager
def single_attempt():
    """Budgeted execution never starts an unreserved provider retry."""
    token = _attempt_limit.set(1)
    try:
        yield
    finally:
        _attempt_limit.reset(token)


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


def with_retries(operation: Callable[[], T], *, attempts: int = 3, base_delay: float = 0.5) -> T:
    attempts = _attempt_limit.get() or attempts
    delay = base_delay
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if attempt >= attempts or not is_retryable(exc):
                raise
            logger.warning("adapter retry %s/%s after %s", attempt, attempts, exc)
            time.sleep(delay)
            delay *= 2
    assert last_error is not None
    raise last_error
