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


def test_cosmic_weather_has_ptbr_fields():
    client = TestClient(main.app)
    resp = client.get("/v1/cosmic-weather?date=2026-11-07", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert "moon_ptbr" in body
    assert body["moon_ptbr"]["signo_ptbr"]
