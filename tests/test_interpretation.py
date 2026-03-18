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


from services.interpretation_engine import get_interpretation


class TestGetInterpretation:
    def test_synastry_aspect_returns_string(self):
        result = get_interpretation(
            planet="moon",
            aspect_type="conjunction",
            other_planet="venus",
            context="synastry",
        )
        assert isinstance(result, str)
        assert len(result) > 10

    def test_natal_planet_sign_returns_string(self):
        result = get_interpretation(planet="sun", sign="scorpio")
        assert isinstance(result, str)
        assert len(result) > 10

    def test_natal_planet_house_returns_string(self):
        result = get_interpretation(planet="moon", house=4)
        assert isinstance(result, str)
        assert len(result) > 10

    def test_unknown_combination_never_returns_empty(self):
        result = get_interpretation(
            planet="jupiter",
            aspect_type="nonexistent_aspect",
            other_planet="uranus",
            context="synastry",
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_synastry_fallback_to_aspect_when_no_synastry_entry(self):
        result = get_interpretation(
            planet="neptune",
            aspect_type="trine",
            other_planet="pluto",
            context="synastry",
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_known_synastry_key_returns_specific_content(self):
        FALLBACK_MARKER = "ativa dinâmicas relacionais e padrões de aprendizado mútuo"
        result = get_interpretation(
            planet="moon",
            aspect_type="conjunction",
            other_planet="venus",
            context="synastry",
        )
        assert isinstance(result, str)
        assert FALLBACK_MARKER not in result, (
            "Chave moon_conjunction_venus deveria retornar conteúdo específico do dict, não o fallback genérico"
        )
