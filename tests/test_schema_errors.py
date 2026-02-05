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


def test_resolve_tz_rejects_natal_fields():
    client = TestClient(main.app)
    payload = {
        "natal_year": 1995,
        "natal_month": 11,
        "natal_day": 7,
        "natal_hour": 22,
        "natal_minute": 56,
        "natal_second": 0,
        "timezone": "America/Sao_Paulo",
    }

    resp = client.post("/v1/time/resolve-tz", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "ASTRO-422"
    assert "resolve-tz" in body["error"]["message"]


def test_transits_rejects_year_payload():
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
        "target_date": "2026-01-09",
    }

    resp = client.post("/v1/chart/transits", json=payload, headers=_auth_headers())
    assert resp.status_code == 422
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "ASTRO-422"
    assert "transits" in body["error"]["message"]
