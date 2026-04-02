import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    yield


def _auth_headers():
    return {"Authorization": "Bearer test-key", "X-User-Id": "u1"}


def test_render_data_accepts_year_payload():
    client = TestClient(main.app)
    payload = {
        "year": 1995,
        "month": 11,
        "day": 7,
        "hour": 22,
        "minute": 56,
        "second": 0,
        "lat": -23.5505,
        "lng": -46.6333,
        "timezone": "America/Sao_Paulo",
    }

    resp = client.post("/v1/chart/render-data", json=payload, headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["planets"]
    assert body["planetas_ptbr"]
    assert body["ascendant"]["sign"]
    assert isinstance(body["ascendant"]["angle_deg"], float)
    assert body["metadados_tecnicos"]["timezone_resolvida"] == "America/Sao_Paulo"
    assert body["metadados_tecnicos"]["datetime_utc_usado"]


def test_render_data_rejects_natal_payload():
    client = TestClient(main.app)
    payload = {
        "natal_year": 1995,
        "natal_month": 11,
        "natal_day": 7,
        "natal_hour": 22,
        "natal_minute": 56,
        "natal_second": 0,
        "lat": -23.5505,
        "lng": -46.6333,
        "timezone": "America/Sao_Paulo",
    }

    resp = client.post("/v1/chart/render-data", json=payload, headers=_auth_headers())
    assert resp.status_code == 422
    assert resp.json()["detail"] == "render-data expects year/month/day/hour/minute/second..."


def test_render_data_accepts_tz_offset_without_timezone():
    client = TestClient(main.app)
    payload = {
        "year": 1995,
        "month": 11,
        "day": 7,
        "hour": 22,
        "minute": 56,
        "second": 0,
        "lat": -23.5505,
        "lng": -46.6333,
        "tz_offset_minutes": -180,
    }

    resp = client.post("/v1/chart/render-data", json=payload, headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["ascendant"]["sign"]
    assert body["metadados_tecnicos"]["tz_offset_minutes_usado"] == -180
