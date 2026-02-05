import pytest
from fastapi.testclient import TestClient

import main
import routes.ai as ai_routes


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    yield


def _auth_headers():
    return {"Authorization": "Bearer test-key", "X-User-Id": "u1"}


def _payload():
    return {
        "user_question": "Como está meu dia?",
        "astro_payload": {"sun": "aries"},
        "tone": "calmo",
        "language": "pt-BR",
    }


def _install_openai_error(monkeypatch, exception_cls):
    class DummyCompletions:
        def create(self, **kwargs):
            raise exception_cls("internal-sensitive-message")

    class DummyChat:
        completions = DummyCompletions()

    class DummyClient:
        chat = DummyChat()

    monkeypatch.setattr(ai_routes, "OpenAI", lambda api_key: DummyClient())


@pytest.mark.parametrize(
    ("exception_name", "status_code", "expected_detail", "retryable"),
    [
        ("AuthenticationError", 503, "Serviço de IA temporariamente indisponível.", True),
        ("RateLimitError", 429, "Limite de uso da IA atingido. Tente novamente em instantes.", True),
        ("APITimeoutError", 504, "Serviço de IA temporariamente indisponível.", True),
        ("APIConnectionError", 502, "Serviço de IA temporariamente indisponível.", True),
        ("APIStatusError", 502, "Serviço de IA temporariamente indisponível.", True),
    ],
)
def test_ai_endpoint_specific_errors_are_safe(
    monkeypatch, exception_name, status_code, expected_detail, retryable
):
    class MappedExc(Exception):
        pass

    monkeypatch.setattr(ai_routes, exception_name, MappedExc)
    _install_openai_error(monkeypatch, MappedExc)

    client = TestClient(main.app)
    resp = client.post("/v1/ai/cosmic-chat", json=_payload(), headers=_auth_headers())

    assert resp.status_code == status_code
    body = resp.json()
    assert body["detail"] == expected_detail
    assert "internal-sensitive-message" not in body["detail"]
    assert body["ok"] is False
    assert body["data"] is None
    assert body["request_id"]
    assert body["error"]["id"].startswith("err_")
    assert body["error"]["code"].startswith("ASTRO-")
    assert body["error"]["message"] == expected_detail
    assert body["error"]["retryable"] is retryable


def test_ai_endpoint_generic_error_hides_internal_details(monkeypatch):
    class DummyCompletions:
        def create(self, **kwargs):
            raise RuntimeError("very sensitive stack info")

    class DummyChat:
        completions = DummyCompletions()

    class DummyClient:
        chat = DummyChat()

    monkeypatch.setattr(ai_routes, "OpenAI", lambda api_key: DummyClient())

    client = TestClient(main.app)
    resp = client.post("/v1/ai/cosmic-chat", json=_payload(), headers=_auth_headers())

    assert resp.status_code == 500
    body = resp.json()
    assert body["detail"] == "Serviço de IA temporariamente indisponível."
    assert "very sensitive" not in body["detail"]
    assert body["error"]["message"] == "Serviço de IA temporariamente indisponível."
