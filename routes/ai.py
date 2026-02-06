from __future__ import annotations

import asyncio
import inspect
import logging
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    InternalServerError,
    RateLimitError,
)

from ai.prompts import build_cosmic_chat_messages
from core.errors import build_error
from services.time_utils import build_time_metadata

from .common import get_auth
from schemas.ai import CosmicChatRequest

router = APIRouter()
logger = logging.getLogger("astro-api")


def _build_ai_error_response(status_code: int, message: str, *, request_id: str, retryable: bool) -> JSONResponse:
    err = build_error(status_code, message, retryable=retryable)
    payload = {
        "ok": False,
        "data": None,
        "error": err.to_response(),
        "detail": message,
        "request_id": request_id,
    }
    return JSONResponse(status_code=status_code, content=payload, headers={"X-Request-Id": request_id})


def initialize_openai_client(app) -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        app.state.openai_client = None
        return

    timeout_s = float(os.getenv("OPENAI_TIMEOUT_S", "35"))
    app.state.openai_client = AsyncOpenAI(api_key=api_key, timeout=timeout_s, max_retries=0)


async def shutdown_openai_client(app) -> None:
    client = getattr(app.state, "openai_client", None)
    if client is None:
        return

    close_result = client.close()
    if inspect.isawaitable(close_result):
        await close_result
    app.state.openai_client = None


async def _create_completion_with_retry(client, *, model: str, messages: list[dict], max_tokens: int, temperature: float):
    max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
    base_backoff_s = float(os.getenv("OPENAI_RETRY_BASE_BACKOFF_S", "0.5"))
    timeout_s = float(os.getenv("OPENAI_TIMEOUT_SECONDS", os.getenv("OPENAI_TIMEOUT_S", "35")))
    transient_errors = (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError)
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout_s,
                ),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError as exc:
            last_error = exc
            logger.warning("cosmic_chat_timeout", extra={"attempt": attempt, "max_retries": max_retries}, exc_info=True)
        except transient_errors as exc:
            last_error = exc
            logger.warning(
                "cosmic_chat_transient_error",
                extra={"attempt": attempt, "max_retries": max_retries},
                exc_info=True,
            )

        if attempt < max_retries:
            await asyncio.sleep(base_backoff_s * (2 ** (attempt - 1)))

    if last_error is not None:
        raise last_error

    raise HTTPException(status_code=504, detail="Serviço de IA temporariamente indisponível. Tente novamente.")


@router.post("/v1/ai/cosmic-chat")
async def cosmic_chat(body: CosmicChatRequest, request: Request, auth=Depends(get_auth)):
    request_id = getattr(request.state, "request_id", None) or str(uuid4())

    async_client = getattr(request.app.state, "openai_client", None)
    if async_client is None:
        logger.error("cosmic_chat_not_configured", extra={"request_id": request_id})
        return _build_ai_error_response(503, "Serviço de IA temporariamente indisponível.", request_id=request_id, retryable=True)

    messages = build_cosmic_chat_messages(
        user_question=body.user_question,
        astro_payload=body.astro_payload,
        tone=body.tone or "calmo, adulto, tecnológico",
        language=body.language or "pt-BR",
    )
    max_tokens = int(os.getenv("OPENAI_MAX_TOKENS_PAID", "1100")) if auth["plan"] != "free" else int(
        os.getenv("OPENAI_MAX_TOKENS_FREE", "600")
    )

    try:
        response = await _create_completion_with_retry(
            async_client,
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )

        return {
            "response": response.choices[0].message.content,
            "usage": response.usage.model_dump(),
            "metadados_tecnicos": {"idioma": body.language or "pt-BR", "fonte_traducao": "backend", **build_time_metadata(None, None, None)},
        }
    except AuthenticationError:
        logger.exception("cosmic_chat_auth_error", extra={"request_id": request_id})
        return _build_ai_error_response(503, "Serviço de IA temporariamente indisponível.", request_id=request_id, retryable=True)
    except RateLimitError:
        logger.exception("cosmic_chat_quota_error", extra={"request_id": request_id})
        return _build_ai_error_response(
            429,
            "Limite de uso da IA atingido. Tente novamente em instantes.",
            request_id=request_id,
            retryable=True,
        )
    except (APITimeoutError, asyncio.TimeoutError):
        logger.exception("cosmic_chat_timeout", extra={"request_id": request_id})
        return _build_ai_error_response(504, "Tempo limite da IA excedido. Tente novamente.", request_id=request_id, retryable=True)
    except (APIConnectionError, APIStatusError):
        logger.exception("cosmic_chat_external_api_error", extra={"request_id": request_id})
        return _build_ai_error_response(502, "Serviço de IA temporariamente indisponível.", request_id=request_id, retryable=True)
    except HTTPException:
        raise
    except (APIError, Exception):
        logger.exception("cosmic_chat_unhandled_error", extra={"request_id": request_id})
        return _build_ai_error_response(
            500,
            "Erro interno ao processar solicitação de IA.",
            request_id=request_id,
            retryable=True,
        )
