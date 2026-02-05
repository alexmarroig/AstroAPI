"""In-memory TTL cache.

This cache is process-local. It is safe for concurrent access from threads
inside the same Python process, but it is not shared across workers/instances.
In distributed environments (multiple processes, containers, or machines), use
an external cache backend (e.g. Redis) if you need global coherence.
"""

import threading
import time
from typing import Any, Callable, Optional

class TTLCache:
    def __init__(
        self,
        sweep_interval_seconds: int = 60,
        time_func: Callable[[], float] = time.time,
    ):
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.RLock()
        self._time_func = time_func
        self._sweep_interval_seconds = sweep_interval_seconds
        self._last_sweep_at = self._time_func()

    def _cleanup_expired(self, now: float) -> int:
        expired_keys = [
            key for key, (expires_at, _) in self._store.items() if now > expires_at
        ]
        for key in expired_keys:
            self._store.pop(key, None)
        return len(expired_keys)

    def _maybe_sweep(self, now: float) -> None:
        if now - self._last_sweep_at >= self._sweep_interval_seconds:
            self._cleanup_expired(now)
            self._last_sweep_at = now

    def sweep(self) -> int:
        """Force a full cleanup pass and return the number of removed keys."""
        with self._lock:
            now = self._time_func()
            removed = self._cleanup_expired(now)
            self._last_sweep_at = now
            return removed

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            now = self._time_func()
            self._maybe_sweep(now)

            item = self._store.get(key)
            if not item:
                return None

            expires_at, value = item
            if now > expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        with self._lock:
            now = self._time_func()
            self._maybe_sweep(now)
            self._store[key] = (now + ttl_seconds, value)

cache = TTLCache()
