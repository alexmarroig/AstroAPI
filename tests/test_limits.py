from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from core.limits import (
    HOURLY_LIMIT,
    InMemoryRateLimitStore,
    check_and_inc,
    get_rate_limit_metrics_snapshot,
    reset_rate_limit_metrics,
)


def test_daily_limit_by_plan_and_endpoint() -> None:
    store = InMemoryRateLimitStore()
    now = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    for _ in range(5):
        ok, msg = check_and_inc(
            "user-free",
            "/v1/ai/cosmic-chat",
            "free",
            now=now,
            store=store,
        )
        assert ok is True
        assert msg == ""

    ok, msg = check_and_inc(
        "user-free",
        "/v1/ai/cosmic-chat",
        "free",
        now=now,
        store=store,
    )
    assert ok is False
    assert "Limite diário atingido" in msg


def test_hourly_window_resets_after_boundary() -> None:
    store = InMemoryRateLimitStore()
    first_window = datetime(2025, 1, 1, 12, 59, 55, tzinfo=timezone.utc)

    for _ in range(HOURLY_LIMIT):
        ok, _ = check_and_inc(
            "hour-user",
            "/v1/cosmic-weather",
            "trial",
            now=first_window,
            store=store,
        )
        assert ok is True

    blocked, msg = check_and_inc(
        "hour-user",
        "/v1/cosmic-weather",
        "trial",
        now=first_window,
        store=store,
    )
    assert blocked is False
    assert "limite horário" in msg.lower()

    next_window = first_window + timedelta(seconds=10)
    ok, msg = check_and_inc(
        "hour-user",
        "/v1/cosmic-weather",
        "trial",
        now=next_window,
        store=store,
    )
    assert ok is True
    assert msg == ""


def test_metrics_are_recorded_per_plan_endpoint_and_window() -> None:
    reset_rate_limit_metrics()
    store = InMemoryRateLimitStore()
    now = datetime(2025, 1, 2, 8, 0, tzinfo=timezone.utc)

    for _ in range(6):
        check_and_inc(
            "metrics-user",
            "/v1/ai/cosmic-chat",
            "free",
            now=now,
            store=store,
        )

    metrics = get_rate_limit_metrics_snapshot()
    assert metrics[("free", "/v1/ai/cosmic-chat", "day")] == 1


def test_concurrent_requests_remain_atomic_on_same_key() -> None:
    store = InMemoryRateLimitStore()
    now = datetime(2025, 1, 3, 11, 0, tzinfo=timezone.utc)

    def invoke_once() -> bool:
        ok, _ = check_and_inc(
            "concurrent-user",
            "/v1/ai/cosmic-chat",
            "free",
            now=now,
            store=store,
        )
        return ok

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(lambda _: invoke_once(), range(50)))

    assert sum(results) == 5
import core.limits as limits


class StubStore:
    def __init__(self, values=None):
        self.values = values or {}
        self.calls = []

    def incr_with_window(self, user_id, endpoint, window, ttl_seconds):
        self.calls.append((user_id, endpoint, window, ttl_seconds))
        key = (user_id, endpoint, window)
        return self.values.get(key, 1)


class AlwaysFailStore:
    def incr_with_window(self, user_id, endpoint, window, ttl_seconds):
        raise RuntimeError("store down")


def test_blocks_when_hour_limit_exceeded():
    limits.reset_rate_limit_metrics()
    store = StubStore(
        {
            ("u1", "*", "hour:2000-01-01-10"): 101,
        }
    )

    original_hour_key = limits._hour_key
    limits._hour_key = lambda: "2000-01-01-10"
    try:
        result = limits._evaluate_limits(store, user_id="u1", endpoint="/v1/chart/natal", plan="free")
    finally:
        limits._hour_key = original_hour_key

    assert result.allowed is False
    assert result.status == "blocked_hour"


def test_blocks_when_day_limit_exceeded():
    store = StubStore(
        {
            ("u1", "*", "hour:2000-01-01-10"): 1,
            ("u1", "/v1/ai/cosmic-chat", "day:2000-01-01"): 6,
        }
    )

    original_hour_key = limits._hour_key
    original_day_key = limits._day_key
    limits._hour_key = lambda: "2000-01-01-10"
    limits._day_key = lambda: "2000-01-01"
    try:
        result = limits._evaluate_limits(store, user_id="u1", endpoint="/v1/ai/cosmic-chat", plan="free")
    finally:
        limits._hour_key = original_hour_key
        limits._day_key = original_day_key

    assert result.allowed is False
    assert result.status == "blocked_day"
    assert "5/dia" in result.message


def test_allows_and_emits_allowed_metric():
    limits.configure_rate_limit_store(StubStore())
    limits.reset_rate_limit_metrics()

    ok, msg = limits.check_and_inc("u1", "/v1/chart/natal", "trial")

    assert ok is True
    assert msg == ""
    assert limits.get_rate_limit_metrics()["allowed"] == 1


def test_fallback_when_store_errors():
    limits.configure_rate_limit_store(AlwaysFailStore())
    limits.reset_rate_limit_metrics()

    ok, _ = limits.check_and_inc("u2", "/v1/chart/natal", "trial")

    assert ok is True
    assert limits.get_rate_limit_metrics()["allowed"] == 1


def test_plan_limits_preserved():
    assert limits._daily_limit_for_plan("free", "/v1/ai/cosmic-chat") == 5
    assert limits._daily_limit_for_plan("trial", "/v1/ai/cosmic-chat") == 100
    assert limits._daily_limit_for_plan("premium", "/v1/ai/cosmic-chat") == 1000
