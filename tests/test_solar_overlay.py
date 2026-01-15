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


def test_solar_return_overlay_shape():
    client = TestClient(main.app)
    payload = {
        "natal": {
            "data": "1995-11-07",
            "hora": "22:56:00",
            "timezone": "America/Sao_Paulo",
            "local": {"nome": "São Paulo", "lat": -23.5505, "lon": -46.6333, "alt_m": 760},
        },
        "alvo": {
            "ano": 2026,
            "timezone": "America/Sao_Paulo",
            "local": {"nome": "São Paulo", "lat": -23.5505, "lon": -46.6333, "alt_m": 760},
        },
        "rs": {"year": 2026},
        "preferencias": {"perfil": "padrao"},
    }

    resp = client.post("/v1/solar-return/overlay", json=payload, headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert "rs_em_casas_natais" in body
    assert "natal_em_casas_rs" in body
    assert "aspectos_rs_x_natal" in body
    assert "metadados" in body
