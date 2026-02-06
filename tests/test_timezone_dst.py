from datetime import datetime

import pytest
from fastapi.testclient import TestClient

import main
from core import timezone_utils as core_timezone_utils
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


def test_validate_local_datetime_dst_end_fold_zero_and_one_offsets():
    fold0 = timezone_utils.validate_local_datetime(
        datetime(2024, 11, 3, 1, 30), "America/New_York", strict=False
    )
    assert fold0.fold == 0
    assert fold0.tz_offset_minutes == -240


def test_core_localize_with_zoneinfo_fold_zero_and_one():
    local_dt = datetime(2024, 11, 3, 1, 30)
    fold0_dt, fold0_info = core_timezone_utils.localize_with_zoneinfo(
        local_dt,
        "America/New_York",
        strict=False,
        prefer_fold=0,
    )
    fold1_dt, fold1_info = core_timezone_utils.localize_with_zoneinfo(
        local_dt,
        "America/New_York",
        strict=False,
        prefer_fold=1,
    )

    assert fold0_info["fold_used"] == 0
    assert fold1_info["fold_used"] == 1
    assert int(fold0_dt.utcoffset().total_seconds() // 60) == -240
    assert int(fold1_dt.utcoffset().total_seconds() // 60) == -300


def test_validate_local_datetime_nonexistent_adjusts_one_hour():
    result = timezone_utils.validate_local_datetime(
        datetime(2024, 3, 10, 2, 30), "America/New_York", strict=False
    )
    assert result.warning and result.warning["code"] == "nonexistent_local_time"
    assert result.adjustment_minutes == 30
    assert result.resolved_datetime.isoformat() == "2024-03-10T03:00:00"


def test_core_localize_with_zoneinfo_nonexistent_strict_raises():
    with pytest.raises(core_timezone_utils.TimezoneResolutionError):
        core_timezone_utils.localize_with_zoneinfo(
            datetime(2024, 3, 10, 2, 30),
            "America/New_York",
            strict=True,
        )
