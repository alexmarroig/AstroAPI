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


def test_interpretation_shape():
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
    resp = client.post("/v1/interpretation/natal", json=payload, headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["titulo"] == "Resumo Geral do Mapa"
    assert len(body["sintese"]) >= 3
    assert body["planetas_com_maior_peso"]
