import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import main


def test_health_ok():
    client = TestClient(main.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True



def test_system_health_detailed():
    client = TestClient(main.app)
    resp = client.get("/v1/system/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "ok"
    assert "openai_status" in body["data"]
