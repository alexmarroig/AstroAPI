import asyncio

from fastapi.testclient import TestClient

import main


class _MockUsage:
    def model_dump(self):
        return {"total_tokens": 10}


class _MockResponse:
    def __init__(self, content: str = "ok"):
        self.choices = [type("Choice", (), {"message": type("Msg", (), {"content": content})()})()]
        self.usage = _MockUsage()


class _MockCompletions:
    def __init__(self, behavior):
        self._behavior = behavior

    async def create(self, **kwargs):
        return await self._behavior(**kwargs)


class _MockChat:
    def __init__(self, behavior):
        self.completions = _MockCompletions(behavior)


class _MockOpenAIClient:
    def __init__(self, behavior):
        self.chat = _MockChat(behavior)

    async def close(self):
        return None


class _Headers:
    @staticmethod
    def build(user_id: str = "test-user"):
        return {
            "Authorization": "Bearer test-api-key",
            "X-User-Id": user_id,
        }


def _payload():
    return {
        "user_question": "Como está meu momento?",
        "astro_payload": {"sun_sign": "Aquário"},
        "language": "pt-BR",
    }


def test_cosmic_chat_timeout_returns_gateway_timeout(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "1")
    monkeypatch.setenv("OPENAI_TIMEOUT_S", "0.01")

    async def _timeout_behavior(**kwargs):
        raise asyncio.TimeoutError("upstream timeout")

    with TestClient(main.app) as client:
        main.app.state.openai_client = _MockOpenAIClient(_timeout_behavior)

        resp = client.post("/v1/ai/cosmic-chat", headers=_Headers.build("timeout-user"), json=_payload())

    assert resp.status_code == 504
    assert "temporariamente indisponível" in resp.json()["detail"].lower()


def test_cosmic_chat_generic_error_is_sanitized(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "1")

    async def _error_behavior(**kwargs):
        raise ValueError("segredo_interno")

    with TestClient(main.app) as client:
        main.app.state.openai_client = _MockOpenAIClient(_error_behavior)

        resp = client.post("/v1/ai/cosmic-chat", headers=_Headers.build("error-user"), json=_payload())

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Erro interno ao processar solicitação de IA."
    assert "segredo_interno" not in resp.text
