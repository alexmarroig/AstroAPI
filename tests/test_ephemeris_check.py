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


def test_ephemeris_check_compares_against_swiss_ephemeris():
    client = TestClient(main.app)
    payload = {
        "datetime_local": "2024-01-01T12:00:00",
        "timezone": "Etc/UTC",
        "lat": 0.0,
        "lng": 0.0,
    }

    resp = client.post("/v1/diagnostics/ephemeris-check", json=payload, headers=_auth_headers())
    assert resp.status_code == 200

    body = resp.json()
    assert body["tz_offset_minutes"] == 0
    assert body["items"], "payload must list planets compared"

    for item in body["items"]:
        assert item["delta_deg_abs"] < 0.05, item


def test_ephemeris_check_rejects_invalid_timezone():
    client = TestClient(main.app)
    payload = {
        "datetime_local": "2024-01-01T12:00:00",
        "timezone": "Mars/Crater",
        "lat": 0.0,
        "lng": 0.0,
    }

    resp = client.post("/v1/diagnostics/ephemeris-check", json=payload, headers=_auth_headers())
    assert resp.status_code == 400

    body = resp.json()
    assert body["ok"] is False
    assert body["message"] == "Timezone inválido: Mars/Crater"
    assert body["error_code"] == "ephemeris_check_invalid_input"
    assert body["request_id"]


def test_ephemeris_check_returns_500_for_processing_error(monkeypatch):
    client = TestClient(main.app)
    payload = {
        "datetime_local": "2024-01-01T12:00:00",
        "timezone": "Etc/UTC",
        "lat": 0.0,
        "lng": 0.0,
    }

    def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("routes.diagnostics.compute_chart", _raise)

    resp = client.post("/v1/diagnostics/ephemeris-check", json=payload, headers=_auth_headers())
    assert resp.status_code == 500

    body = resp.json()
    assert body["ok"] is False
    assert body["message"] == "Não foi possível validar a efeméride neste momento"
    assert body["error_code"] == "ephemeris_check_failed"
    assert body["request_id"]
