import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ADMIN_USER_IDS", "admin@local")


def _h(user_id: str = "free@local"):
    return {"Authorization": "Bearer test-key", "X-User-Id": user_id}


def test_billing_entitlements_free():
    client = TestClient(main.app)
    resp = client.get("/v1/billing/entitlements", headers=_h("free@local"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["entitlements"]["admin_dashboard"] is False


def test_astro_chart_envelope():
    client = TestClient(main.app)
    payload = {
        "year": 1990,
        "month": 1,
        "day": 1,
        "hour": 12,
        "minute": 0,
        "second": 0,
        "lat": -23.55,
        "lng": -46.63,
        "tz_offset_minutes": -180,
        "house_system": "P",
        "zodiac_type": "tropical",
    }
    resp = client.post("/v1/astro/chart", json=payload, headers=_h("premium@local"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "planets" in body["data"]


def test_oracle_chat_fallback_works():
    client = TestClient(main.app)
    resp = client.post(
        "/v1/oracle/chat",
        json={"message": "Como está meu dia?", "context": {}, "idempotency_key": "k1"},
        headers=_h("free@local"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "reply" in body["data"]


def test_admin_dashboard_requires_admin():
    client = TestClient(main.app)
    denied = client.get("/v1/admin/dashboard", headers=_h("free@local"))
    assert denied.status_code == 403

    allowed = client.get("/v1/admin/dashboard", headers=_h("admin@local"))
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True
