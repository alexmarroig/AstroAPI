import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Protocol


FREE_LIMITS = {
    "/v1/ai/cosmic-chat": 5,
    "/v1/chart/transits": 30,
    "/v1/cosmic-weather": 60,
    "/v1/chart/natal": 20,
    "/v1/chart/render-data": 60,
}

TRIAL_LIMITS = {
    "/v1/ai/cosmic-chat": 100,
    "/v1/chart/transits": 500,
    "/v1/cosmic-weather": 500,
    "/v1/chart/natal": 200,
    "/v1/chart/render-data": 500,
}

PREMIUM_LIMITS = {
    "/v1/ai/cosmic-chat": 1000,
    "/v1/chart/transits": 5000,
    "/v1/cosmic-weather": 5000,
    "/v1/chart/natal": 2000,
    "/v1/chart/render-data": 5000,
}

HOURLY_LIMIT = 100


class RateLimitStorage(Protocol):
    def incr_with_ttl(self, key: str, ttl_seconds: int) -> int:
        """Atomically increment key and apply expiry when key is created."""


class MemoryRateLimitStorage:
    """Optional fallback backend when Redis is not available."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counts: dict[str, int] = {}
        self._expires_at: dict[str, float] = {}

    def incr_with_ttl(self, key: str, ttl_seconds: int) -> int:
        now = time.time()
        with self._lock:
            expiry = self._expires_at.get(key)
            if expiry is not None and expiry <= now:
                self._counts.pop(key, None)
                self._expires_at.pop(key, None)

            next_value = self._counts.get(key, 0) + 1
            self._counts[key] = next_value
            if next_value == 1:
                self._expires_at[key] = now + max(ttl_seconds, 1)
            return next_value


class RedisRateLimitStorage:
    _LUA_INCR_EXPIRE = """
    local current = redis.call('INCR', KEYS[1])
    if current == 1 then
      redis.call('EXPIRE', KEYS[1], ARGV[1])
    end
    return current
    """

    def __init__(self, client) -> None:
        self._client = client

    def incr_with_ttl(self, key: str, ttl_seconds: int) -> int:
        ttl = max(int(ttl_seconds), 1)
        value = self._client.eval(self._LUA_INCR_EXPIRE, 1, key, ttl)
        return int(value)


@dataclass
class RateLimitMetrics:
    exceeded: defaultdict[tuple[str, str, str], int]
    _lock: Lock

    def __init__(self) -> None:
        self.exceeded = defaultdict(int)
        self._lock = Lock()

    def record_exceeded(self, plan: str, endpoint: str, window: str) -> None:
        with self._lock:
            self.exceeded[(plan, endpoint, window)] += 1

    def snapshot(self) -> dict[tuple[str, str, str], int]:
        with self._lock:
            return dict(self.exceeded)


_metrics = RateLimitMetrics()
_memory_fallback_storage = MemoryRateLimitStorage()
_default_storage: RateLimitStorage | None = None


def _resolve_limits(plan: str) -> tuple[dict[str, int], int]:
    if plan == "free":
        return FREE_LIMITS, 50
    if plan == "trial":
        return TRIAL_LIMITS, 200
    return PREMIUM_LIMITS, 200


def _window_boundaries(now: datetime) -> tuple[int, int, str, str]:
    now_utc = now.astimezone(timezone.utc)

    next_hour = (now_utc.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    next_day = (now_utc.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))

    hour_ttl = int((next_hour - now_utc).total_seconds())
    day_ttl = int((next_day - now_utc).total_seconds())

    hour_window = now_utc.strftime("%Y%m%d%H")
    day_window = now_utc.strftime("%Y%m%d")

    return max(hour_ttl, 1), max(day_ttl, 1), hour_window, day_window


def _hour_storage_key(user_id: str, hour_window: str) -> str:
    return f"rl:hour:{hour_window}:{user_id}"


def _day_storage_key(user_id: str, endpoint: str, day_window: str) -> str:
    return f"rl:day:{day_window}:{user_id}:{endpoint}"


def _build_redis_storage() -> RateLimitStorage | None:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return None

    try:
        import redis  # type: ignore
    except Exception:
        return None

    try:
        client = redis.Redis.from_url(redis_url, decode_responses=False)
        return RedisRateLimitStorage(client)
    except Exception:
        return None


def _get_default_storage() -> RateLimitStorage:
    global _default_storage
    if _default_storage is not None:
        return _default_storage

    backend = os.getenv("RATE_LIMIT_BACKEND", "redis").lower()
    if backend == "redis":
        redis_storage = _build_redis_storage()
        if redis_storage is not None:
            _default_storage = redis_storage
            return _default_storage

    _default_storage = _memory_fallback_storage
    return _default_storage


def check_and_inc(
    user_id: str,
    endpoint: str,
    plan: str,
    *,
    now: datetime | None = None,
    storage: RateLimitStorage | None = None,
) -> tuple[bool, str]:
    current_time = now or datetime.now(timezone.utc)
    hour_ttl, day_ttl, hour_window, day_window = _window_boundaries(current_time)

    active_storage = storage or _get_default_storage()

    hourly_count = active_storage.incr_with_ttl(
        _hour_storage_key(user_id, hour_window),
        hour_ttl,
    )
    if hourly_count > HOURLY_LIMIT:
        _metrics.record_exceeded(plan, endpoint, "hour")
        return (
            False,
            "Você alcançou o limite horário de 100 requisições. Respire e tente novamente em instantes.",
        )

    limits, default_limit = _resolve_limits(plan)
    daily_limit = limits.get(endpoint, default_limit)

    daily_count = active_storage.incr_with_ttl(
        _day_storage_key(user_id, endpoint, day_window),
        day_ttl,
    )
    if daily_count > daily_limit:
        _metrics.record_exceeded(plan, endpoint, "day")
        return False, f"Limite diário atingido para este recurso ({daily_limit}/dia)."

    return True, ""


def get_rate_limit_metrics_snapshot() -> dict[tuple[str, str, str], int]:
    return _metrics.snapshot()


def reset_rate_limit_metrics() -> None:
    global _metrics
    _metrics = RateLimitMetrics()
