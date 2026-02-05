import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    status: str
    message: str = ""


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
            exp = self._expirations.get(key)
            if exp is not None and exp <= now:
                self._counts.pop(key, None)
                self._expirations.pop(key, None)

            self._counts[key] += 1
            if key not in self._expirations:
                self._expirations[key] = now + ttl_seconds

            return self._counts[key]


class RedisRateLimitStore:
    """Redis backend with atomic increment + TTL assignment per fixed window key."""

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
        pipe = self._client.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl_seconds, nx=True)
        count, _ = pipe.execute()
        return int(count)


_metrics: dict[str, int] = defaultdict(int)


def get_rate_limit_metrics() -> dict[str, int]:
    return dict(_metrics)


def reset_rate_limit_metrics() -> None:
    _metrics.clear()


def _inc_metric(status: str) -> None:
    _metrics[status] += 1


def _daily_limit_for_plan(plan: str, endpoint: str) -> int:
    if plan == "free":
        limits = {
            "/v1/ai/cosmic-chat": 5,
            "/v1/chart/transits": 30,
            "/v1/cosmic-weather": 60,
            "/v1/chart/natal": 20,
            "/v1/chart/render-data": 60,
        }
    elif plan == "trial":
        limits = {
            "/v1/ai/cosmic-chat": 100,
            "/v1/chart/transits": 500,
            "/v1/cosmic-weather": 500,
            "/v1/chart/natal": 200,
            "/v1/chart/render-data": 500,
        }
    else:  # premium
        limits = {
            "/v1/ai/cosmic-chat": 1000,
            "/v1/chart/transits": 5000,
            "/v1/cosmic-weather": 5000,
            "/v1/chart/natal": 2000,
            "/v1/chart/render-data": 5000,
        }

    return limits.get(endpoint, 200 if plan != "free" else 50)


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
        import redis  # type: ignore

        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return RedisRateLimitStore(client)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Rate-limit Redis indisponível, usando fallback em memória: %s", exc)
        return None


_store: RateLimitStore = _create_redis_store_from_env() or InMemoryRateLimitStore()


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
    hourly_limit = 100
    if hour_count > hourly_limit:
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


def check_and_inc(user_id: str, endpoint: str, plan: str) -> tuple[bool, str]:
    global _store

    try:
        result = _evaluate_limits(_store, user_id=user_id, endpoint=endpoint, plan=plan)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Erro no backend principal de rate-limit, usando fallback em memória: %s", exc)
        fallback = InMemoryRateLimitStore()
        _store = fallback
        result = _evaluate_limits(fallback, user_id=user_id, endpoint=endpoint, plan=plan)

    _inc_metric(result.status)
    return result.allowed, result.message
