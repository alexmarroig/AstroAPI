import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Protocol

logger = logging.getLogger(__name__)

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


class RateLimitStore(Protocol):
    def incr_with_window(
        self,
        user_id: str,
        endpoint: str,
        window: str,
        ttl_seconds: int,
    ) -> int:
        """Increment and return usage count for the provided window."""


class InMemoryRateLimitStore:
    """Thread-safe in-memory backend used as fallback and default for tests."""

    def __init__(self) -> None:
        self._counts: dict[tuple[str, str, str], int] = defaultdict(int)
        self._expirations: dict[tuple[str, str, str], float] = {}
        self._lock = Lock()

    def incr_with_window(
        self,
        user_id: str,
        endpoint: str,
        window: str,
        ttl_seconds: int,
    ) -> int:
        key = (window, user_id, endpoint)
        now = time.time()

        with self._lock:
            expiration = self._expirations.get(key)
            if expiration is not None and expiration <= now:
                self._counts.pop(key, None)
                self._expirations.pop(key, None)

            self._counts[key] += 1
            if key not in self._expirations:
                self._expirations[key] = now + max(ttl_seconds, 1)

            return self._counts[key]


class RedisRateLimitStore:
    """Redis backend with atomic increment + TTL assignment per fixed window key."""

    _LUA_INCR_EXPIRE = """
    local current = redis.call('INCR', KEYS[1])
    if current == 1 then
      redis.call('EXPIRE', KEYS[1], ARGV[1])
    end
    return current
    """

    def __init__(self, client) -> None:
        self._client = client

    def _key(self, user_id: str, endpoint: str, window: str) -> str:
        return f"ratelimit:{window}:{user_id}:{endpoint}"

    def incr_with_window(
        self,
        user_id: str,
        endpoint: str,
        window: str,
        ttl_seconds: int,
    ) -> int:
        key = self._key(user_id=user_id, endpoint=endpoint, window=window)
        ttl = max(int(ttl_seconds), 1)
        count = self._client.eval(self._LUA_INCR_EXPIRE, 1, key, ttl)
        return int(count)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    status: str
    message: str = ""


@dataclass
class DetailedRateLimitMetrics:
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


_detailed_metrics = DetailedRateLimitMetrics()
_simple_metrics: defaultdict[str, int] = defaultdict(int)
_store: RateLimitStore | None = None


def _resolve_limits(plan: str) -> tuple[dict[str, int], int]:
    if plan == "free":
        return FREE_LIMITS, 50
    if plan == "trial":
        return TRIAL_LIMITS, 200
    return PREMIUM_LIMITS, 200


def _daily_limit_for_plan(plan: str, endpoint: str) -> int:
    limits, default_limit = _resolve_limits(plan)
    return limits.get(endpoint, default_limit)


def _window_boundaries(now: datetime) -> tuple[int, int, str, str]:
    now_utc = now.astimezone(timezone.utc)

    next_hour = now_utc.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    next_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    hour_ttl = int((next_hour - now_utc).total_seconds())
    day_ttl = int((next_day - now_utc).total_seconds())

    hour_window = now_utc.strftime("%Y%m%d%H")
    day_window = now_utc.strftime("%Y%m%d")

    return max(hour_ttl, 1), max(day_ttl, 1), hour_window, day_window


def _day_key() -> str:
    t = time.gmtime()
    return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"


def _hour_key() -> str:
    t = time.gmtime()
    return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}-{t.tm_hour:02d}"


def _seconds_to_next_hour(now: float | None = None) -> int:
    now = now or time.time()
    return max(1, int(((int(now) // 3600) + 1) * 3600 - now))


def _seconds_to_next_day(now: float | None = None) -> int:
    now = now or time.time()
    return max(1, int(((int(now) // 86400) + 1) * 86400 - now))


def _create_redis_store_from_env() -> RateLimitStore | None:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return None

    try:
        redis_module = __import__("redis")
        client = redis_module.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return RedisRateLimitStore(client)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Rate-limit Redis indisponível, usando fallback em memória: %s", exc)
        return None


def configure_rate_limit_store(store: RateLimitStore) -> None:
    global _store
    _store = store


def reset_rate_limit_store() -> None:
    global _store
    _store = _create_redis_store_from_env() or InMemoryRateLimitStore()


def _evaluate_limits(store: RateLimitStore, user_id: str, endpoint: str, plan: str) -> RateLimitResult:
    hour_count = store.incr_with_window(
        user_id=user_id,
        endpoint="*",
        window=f"hour:{_hour_key()}",
        ttl_seconds=_seconds_to_next_hour(),
    )
    if hour_count > HOURLY_LIMIT:
        return RateLimitResult(
            allowed=False,
            status="blocked_hour",
            message="Você alcançou o limite horário de 100 requisições. Respire e tente novamente em instantes.",
        )

    daily_limit = _daily_limit_for_plan(plan=plan, endpoint=endpoint)
    day_count = store.incr_with_window(
        user_id=user_id,
        endpoint=endpoint,
        window=f"day:{_day_key()}",
        ttl_seconds=_seconds_to_next_day(),
    )
    if day_count > daily_limit:
        return RateLimitResult(
            allowed=False,
            status="blocked_day",
            message=f"Limite diário atingido para este recurso ({daily_limit}/dia).",
        )

    return RateLimitResult(allowed=True, status="allowed")


def _inc_metric(status: str) -> None:
    _simple_metrics[status] += 1


def get_rate_limit_metrics() -> dict[str, int]:
    return dict(_simple_metrics)


def get_rate_limit_metrics_snapshot() -> dict[tuple[str, str, str], int]:
    return _detailed_metrics.snapshot()


def reset_rate_limit_metrics() -> None:
    global _detailed_metrics
    _detailed_metrics = DetailedRateLimitMetrics()
    _simple_metrics.clear()


def check_and_inc(
    user_id: str,
    endpoint: str,
    plan: str,
    *,
    now: datetime | None = None,
    store: RateLimitStore | None = None,
) -> tuple[bool, str]:
    global _store
    if now is not None or store is not None:
        current_time = now or datetime.now(timezone.utc)
        hour_ttl, day_ttl, hour_window, day_window = _window_boundaries(current_time)
        active_store = store or _store or InMemoryRateLimitStore()

        hour_count = active_store.incr_with_window(
            user_id=user_id,
            endpoint="*",
            window=f"hour:{hour_window}",
            ttl_seconds=hour_ttl,
        )
        if hour_count > HOURLY_LIMIT:
            _detailed_metrics.record_exceeded(plan, endpoint, "hour")
            _inc_metric("blocked_hour")
            return (
                False,
                "Você alcançou o limite horário de 100 requisições. Respire e tente novamente em instantes.",
            )

        daily_limit = _daily_limit_for_plan(plan=plan, endpoint=endpoint)
        day_count = active_store.incr_with_window(
            user_id=user_id,
            endpoint=endpoint,
            window=f"day:{day_window}",
            ttl_seconds=day_ttl,
        )
        if day_count > daily_limit:
            _detailed_metrics.record_exceeded(plan, endpoint, "day")
            _inc_metric("blocked_day")
            return False, f"Limite diário atingido para este recurso ({daily_limit}/dia)."

        _inc_metric("allowed")
        return True, ""

    if _store is None:
        _store = _create_redis_store_from_env() or InMemoryRateLimitStore()

    try:
        result = _evaluate_limits(_store, user_id=user_id, endpoint=endpoint, plan=plan)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Erro no backend principal de rate-limit, usando fallback em memória: %s", exc)
        fallback = InMemoryRateLimitStore()
        _store = fallback
        result = _evaluate_limits(fallback, user_id=user_id, endpoint=endpoint, plan=plan)

    _inc_metric(result.status)
    if result.status == "blocked_hour":
        _detailed_metrics.record_exceeded(plan, endpoint, "hour")
    elif result.status == "blocked_day":
        _detailed_metrics.record_exceeded(plan, endpoint, "day")

    return result.allowed, result.message
