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


def test_cosmic_weather_has_new_fields():
    client = TestClient(main.app)
    resp = client.get(
        "/v1/cosmic-weather?date=2024-05-01&timezone=America/Sao_Paulo",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "top_event" in body
    assert "trigger_event" in body
    assert "secondary_events" in body
    assert "summary" in body
