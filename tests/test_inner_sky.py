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


def test_daily_analysis_ok():
    client = TestClient(main.app)
    resp = client.get("/api/daily-analysis/2024-01-01", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "lunarPhase" in body


def test_astral_oracle_quick_answer():
    client = TestClient(main.app)
    payload = {
        "userId": "u1",
        "question": "Como é meu dia?",
        "context": {"date": "2024-01-01"},
    }
    resp = client.post("/api/chat/astral-oracle", json=payload, headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["theme"] == "dia"
    assert "timestamp" in body


def test_solar_return_ok():
    client = TestClient(main.app)
    resp = client.get(
        "/api/solar-return",
        params={
            "natal_year": 1995,
            "natal_month": 11,
            "natal_day": 7,
            "natal_hour": 22,
            "natal_minute": 56,
            "natal_second": 0,
            "target_year": 2024,
            "lat": -23.5505,
            "lng": -46.6333,
            "timezone": "America/Sao_Paulo",
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "solarReturnDate" in body


def test_lunar_calendar_ok():
    client = TestClient(main.app)
    resp = client.get(
        "/api/lunar-calendar",
        params={"month": 1, "year": 2024},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["phases"]


def test_lunar_calendar_week_range():
    client = TestClient(main.app)
    resp = client.get(
        "/api/lunar-calendar",
        params={"month": 1, "year": 2024, "range": "week"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["phases"]) == 7


def test_secondary_progressions_ok():
    client = TestClient(main.app)
    resp = client.get(
        "/api/secondary-progressions",
        params={
            "natal_year": 1995,
            "natal_month": 11,
            "natal_day": 7,
            "natal_hour": 22,
            "natal_minute": 56,
            "natal_second": 0,
            "lat": -23.5505,
            "lng": -46.6333,
            "timezone": "America/Sao_Paulo",
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "progressedChart" in body
