from __future__ import annotations
import asyncio
import inspect
import os
import logging
from fastapi import APIRouter, Depends, Request, HTTPException
from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)

from .common import get_auth
from schemas.ai import CosmicChatRequest
from ai.prompts import build_cosmic_chat_messages
from services.time_utils import build_time_metadata

router = APIRouter()
logger = logging.getLogger("astro-api")


def initialize_openai_client(app) -> None:
    """Inicializa cliente OpenAI assíncrono singleton por processo."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        app.state.openai_client = None
        return

    timeout_s = float(os.getenv("OPENAI_TIMEOUT_S", "35"))
    app.state.openai_client = AsyncOpenAI(api_key=api_key, timeout=timeout_s)


async def shutdown_openai_client(app) -> None:
    client = getattr(app.state, "openai_client", None)
    if client is None:
        return

    close_result = client.close()
    if inspect.isawaitable(close_result):
        await close_result


async def _create_completion_with_retry(client, *, model: str, messages: list[dict], max_tokens: int, temperature: float):
    max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
    base_backoff_s = float(os.getenv("OPENAI_RETRY_BASE_BACKOFF_S", "0.5"))
    timeout_s = float(os.getenv("OPENAI_TIMEOUT_S", "35"))
    transient_errors = (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError)

    for attempt in range(1, max_retries + 1):
        try:
            return await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            logger.warning("cosmic_chat_timeout", extra={"attempt": attempt, "max_retries": max_retries}, exc_info=True)
        except transient_errors:
            logger.warning("cosmic_chat_transient_error", extra={"attempt": attempt, "max_retries": max_retries}, exc_info=True)

        if attempt < max_retries:
            await asyncio.sleep(base_backoff_s * (2 ** (attempt - 1)))

    raise HTTPException(status_code=504, detail="Serviço de IA temporariamente indisponível. Tente novamente.")

@router.post("/v1/ai/cosmic-chat")
async def cosmic_chat(body: CosmicChatRequest, request: Request, auth=Depends(get_auth)):
    """Inicia um chat interpretativo com IA baseado em dados astrológicos."""
    client = getattr(request.app.state, "openai_client", None)
    if client is None:
        raise HTTPException(status_code=500, detail="IA não configurada.")

    try:
        messages = build_cosmic_chat_messages(
            user_question=body.user_question, astro_payload=body.astro_payload,
            tone=body.tone or "calmo, adulto, tecnológico", language=body.language or "pt-BR"
        )

        max_tokens = int(os.getenv("OPENAI_MAX_TOKENS_PAID", "1100")) if auth["plan"] != "free" else int(os.getenv("OPENAI_MAX_TOKENS_FREE", "600"))

        response = await _create_completion_with_retry(
            client,
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )

        return {
            "response": response.choices[0].message.content,
            "usage": response.usage.model_dump(),
            "metadados_tecnicos": {
                "idioma": "pt-BR", "fonte_traducao": "backend",
                **build_time_metadata(None, None, None)
            }
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("cosmic_chat_error")
        raise HTTPException(status_code=500, detail="Erro interno ao processar solicitação de IA.")
