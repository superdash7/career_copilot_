"""Простой in-memory rate limiter для auth endpoint-ов."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict

try:
    from fastapi import HTTPException
except Exception:  # pragma: no cover
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail


class SlidingWindowRateLimiter:
    """Thread-safe sliding window limiter."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            cutoff = now - self.window_seconds
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.max_requests:
                return False
            q.append(now)
            return True


_limiters: Dict[str, SlidingWindowRateLimiter] = {}
_registry_lock = threading.Lock()


def _get_limiter(limit: int, window_sec: int) -> SlidingWindowRateLimiter:
    key = f"{limit}:{window_sec}"
    with _registry_lock:
        limiter = _limiters.get(key)
        if limiter is None:
            limiter = SlidingWindowRateLimiter(limit, window_sec)
            _limiters[key] = limiter
        return limiter


def check_rate_limit_or_raise(key: str, limit: int, window_sec: int) -> None:
    limiter = _get_limiter(limit=limit, window_sec=window_sec)
    if not limiter.allow(key):
        raise HTTPException(status_code=429, detail="Слишком много попыток. Повторите позже.")
