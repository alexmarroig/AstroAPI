from datetime import datetime

import pytest
from fastapi.testclient import TestClient

import main
from services import timezone_utils


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    yield


def test_validate_local_datetime_dst_end_ambiguous():
    client = TestClient(main.app)
    payload = {
        "datetime_local": "2024-11-03T01:30:00",
        "timezone": "America/New_York",
        "strict": True,
    }

    resp = client.post("/v1/time/validate-local-datetime", json=payload)
    assert resp.status_code == 400

    payload["strict"] = False
    resp = client.post("/v1/time/validate-local-datetime", json=payload)
    assert resp.status_code == 200
    body = resp.json()

    expected = timezone_utils.validate_local_datetime(
        datetime(2024, 11, 3, 1, 30), "America/New_York", strict=False
    )

    assert body["fold"] == expected.fold
    assert body["tz_offset_minutes"] == expected.tz_offset_minutes
    assert body["warning"]["code"] == "ambiguous_local_time"
    assert body["metadados_tecnicos"]["tz_offset_minutes"] == body["tz_offset_minutes"]


def test_validate_local_datetime_dst_start_nonexistent():
    client = TestClient(main.app)
    payload = {
        "datetime_local": "2024-03-10T02:30:00",
        "timezone": "America/New_York",
        "strict": True,
    }

    resp = client.post("/v1/time/validate-local-datetime", json=payload)
    assert resp.status_code == 400

    payload["strict"] = False
    resp = client.post("/v1/time/validate-local-datetime", json=payload)
    assert resp.status_code == 200
    body = resp.json()

    expected = timezone_utils.validate_local_datetime(
        datetime(2024, 3, 10, 2, 30), "America/New_York", strict=False
    )

    assert body["datetime_local"] == expected.resolved_datetime.isoformat()
    assert body["warning"]["code"] == "nonexistent_local_time"
    assert body["warning"]["adjustment_minutes"] == expected.adjustment_minutes
    assert body["utc_datetime"] == expected.utc_datetime.isoformat()
    assert body["metadados_tecnicos"]["ajuste_minutos"] == expected.adjustment_minutes


def test_validate_local_datetime_previous_day_utc():
    client = TestClient(main.app)
    payload = {
        "datetime_local": "2024-01-01T00:00:00",
        "timezone": "Asia/Tokyo",
        "strict": False,
    }

    resp = client.post("/v1/time/validate-local-datetime", json=payload)
    assert resp.status_code == 200
    body = resp.json()

    expected = timezone_utils.validate_local_datetime(
        datetime(2024, 1, 1, 0, 0), "Asia/Tokyo", strict=False
    )

    assert body["utc_datetime"].startswith("2023-12-31")
    assert body["utc_datetime"] == expected.utc_datetime.isoformat()
    assert body["metadados_tecnicos"]["timezone"] == "Asia/Tokyo"
    assert body["metadados_tecnicos"]["tz_offset_minutes"] == expected.tz_offset_minutes
