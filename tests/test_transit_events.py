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


def test_transit_events_shape_and_score():
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
        "house_system": "P",
        "zodiac_type": "tropical",
        "range": {"from": "2026-11-07", "to": "2026-11-08"},
        "preferencias": {"perfil": "padrao"},
    }

    resp = client.post("/v1/transits/events", json=payload, headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert "events" in body
    assert "metadados" in body
    if body["events"]:
        event = body["events"][0]
        assert 0 <= event["impact_score"] <= 100
        assert event["aspecto"] in {"Conjunção", "Oposição", "Quadratura", "Trígono", "Sextil"}
