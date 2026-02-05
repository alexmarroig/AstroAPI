from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from core.limits import (
    HOURLY_LIMIT,
    MemoryRateLimitStorage,
    check_and_inc,
    get_rate_limit_metrics_snapshot,
    reset_rate_limit_metrics,
)


def test_daily_limit_by_plan_and_endpoint() -> None:
    storage = MemoryRateLimitStorage()
    now = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    for _ in range(5):
        ok, msg = check_and_inc(
            "user-free",
            "/v1/ai/cosmic-chat",
            "free",
            now=now,
            storage=storage,
        )
        assert ok is True
        assert msg == ""

    ok, msg = check_and_inc(
        "user-free",
        "/v1/ai/cosmic-chat",
        "free",
        now=now,
        storage=storage,
    )
    assert ok is False
    assert "Limite diário atingido" in msg


def test_hourly_window_resets_after_boundary() -> None:
    storage = MemoryRateLimitStorage()
    first_window = datetime(2025, 1, 1, 12, 59, 55, tzinfo=timezone.utc)

    for _ in range(HOURLY_LIMIT):
        ok, _ = check_and_inc(
            "hour-user",
            "/v1/cosmic-weather",
            "trial",
            now=first_window,
            storage=storage,
        )
        assert ok is True

    blocked, msg = check_and_inc(
        "hour-user",
        "/v1/cosmic-weather",
        "trial",
        now=first_window,
        storage=storage,
    )
    assert blocked is False
    assert "limite horário" in msg.lower()

    next_window = first_window + timedelta(seconds=10)
    ok, msg = check_and_inc(
        "hour-user",
        "/v1/cosmic-weather",
        "trial",
        now=next_window,
        storage=storage,
    )
    assert ok is True
    assert msg == ""


def test_metrics_are_recorded_per_plan_endpoint_and_window() -> None:
    reset_rate_limit_metrics()
    storage = MemoryRateLimitStorage()
    now = datetime(2025, 1, 2, 8, 0, tzinfo=timezone.utc)

    for _ in range(6):
        check_and_inc(
            "metrics-user",
            "/v1/ai/cosmic-chat",
            "free",
            now=now,
            storage=storage,
        )

    metrics = get_rate_limit_metrics_snapshot()
    assert metrics[("free", "/v1/ai/cosmic-chat", "day")] == 1


def test_concurrent_requests_remain_atomic_on_same_key() -> None:
    storage = MemoryRateLimitStorage()
    now = datetime(2025, 1, 3, 11, 0, tzinfo=timezone.utc)

    def invoke_once() -> bool:
        ok, _ = check_and_inc(
            "concurrent-user",
            "/v1/ai/cosmic-chat",
            "free",
            now=now,
            storage=storage,
        )
        return ok

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(lambda _: invoke_once(), range(50)))

    assert sum(results) == 5
