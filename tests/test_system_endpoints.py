import os

from fastapi.testclient import TestClient

import main


def test_system_endpoints_requires_flag(monkeypatch):
    client = TestClient(main.app)
    monkeypatch.delenv("ENABLE_ENDPOINTS_LIST", raising=False)
    resp = client.get("/v1/system/endpoints")
    assert resp.status_code == 404


def test_system_endpoints_enabled(monkeypatch):
    client = TestClient(main.app)
    monkeypatch.setenv("ENABLE_ENDPOINTS_LIST", "1")
    resp = client.get("/v1/system/endpoints")
    assert resp.status_code == 200
    data = resp.json()
    assert "endpoints" in data
    assert isinstance(data["endpoints"], list)
