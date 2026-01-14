import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("SOLAR_RETURN_ENGINE", "v2")
    yield


def _auth_headers():
    return {"Authorization": "Bearer test-key", "X-User-Id": "u1"}


def _payload():
    return {
        "natal": {
            "data": "1995-11-07",
            "hora": "22:56:00",
            "timezone": "America/Sao_Paulo",
            "local": {"nome": "São Paulo, BR", "lat": -23.5505, "lon": -46.6333, "alt_m": 760},
        },
        "alvo": {
            "ano": 2026,
            "timezone": "America/Sao_Paulo",
            "local": {"nome": "São Paulo, BR", "lat": -23.5505, "lon": -46.6333, "alt_m": 760},
        },
        "preferencias": {"zodiaco": "tropical", "sistema_casas": "P"},
    }


def _payload_missing_time():
    payload = _payload()
    payload["natal"] = {**payload["natal"]}
    payload["natal"].pop("hora", None)
    return payload


def test_solar_return_structure():
    client = TestClient(main.app)
    resp = client.post("/v1/solar-return/calculate", json=_payload(), headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert "metadados_tecnicos" in body
    assert "mapa_revolucao" in body
    assert "planetas" in body["mapa_revolucao"]
    assert "planetas_ptbr" in body["mapa_revolucao"]
    assert "aspectos" in body["mapa_revolucao"]
    assert "aspectos_ptbr" in body["mapa_revolucao"]
    assert "casas_ptbr" in body["mapa_revolucao"]
    assert "areas_ativadas" in body
    assert "destaques" in body
    assert len(body["areas_ativadas"]) >= 3
    assert len(body["destaques"]) >= 3


def test_solar_return_matches_sun_longitude():
    client = TestClient(main.app)
    resp = client.post("/v1/solar-return/calculate", json=_payload(), headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    delta = body["metadados_tecnicos"]["delta_longitude_graus"]
    assert delta <= 0.01


def test_solar_return_missing_time_warns():
    client = TestClient(main.app)
    resp = client.post(
        "/v1/solar-return/calculate", json=_payload_missing_time(), headers=_auth_headers()
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["warnings"] == ["hora ausente; assumido 12:00:00"]
