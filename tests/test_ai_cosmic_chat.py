import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APITimeoutError

import main
import routes.ai as ai_route


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "5")
    yield


def _auth_headers():
    return {"Authorization": "Bearer test-key", "X-User-Id": "u1"}


def _payload():
    return {
        "user_question": "Como está minha energia hoje?",
        "astro_payload": {"sun_sign": "Aquário"},
        "tone": "claro",
        "language": "pt-BR",
    }


def test_cosmic_chat_success_with_async_mock(monkeypatch):
    captured = {}

    class FakeUsage:
        def model_dump(self):
            return {"total_tokens": 42}

    class FakeMessage:
        content = "Resposta mockada"

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeAsyncOpenAI:
        def __init__(self, api_key):
            assert api_key == "dummy-key"
            self.chat = FakeChat()

    monkeypatch.setattr(ai_route, "AsyncOpenAI", FakeAsyncOpenAI)

    client = TestClient(main.app)
    resp = client.post("/v1/ai/cosmic-chat", json=_payload(), headers=_auth_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["response"] == "Resposta mockada"
    assert body["usage"]["total_tokens"] == 42
    assert captured["timeout"] == 5.0


def test_cosmic_chat_timeout_returns_standard_error(monkeypatch):
    class FakeCompletions:
        async def create(self, **kwargs):
            raise APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))

    class FakeChat:
        completions = FakeCompletions()

    class FakeAsyncOpenAI:
        def __init__(self, api_key):
            self.chat = FakeChat()

    monkeypatch.setattr(ai_route, "AsyncOpenAI", FakeAsyncOpenAI)

    client = TestClient(main.app)
    resp = client.post("/v1/ai/cosmic-chat", json=_payload(), headers=_auth_headers())

    assert resp.status_code == 504
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "ASTRO-500"
    assert body["detail"] == "Tempo limite da IA excedido. Tente novamente."
