from __future__ import annotations
import os
import logging
from uuid import uuid4
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from openai import OpenAI
from openai import APIConnectionError, APITimeoutError, APIStatusError, AuthenticationError, RateLimitError

from .common import get_auth
from core.errors import build_error
from schemas.ai import CosmicChatRequest
from ai.prompts import build_cosmic_chat_messages
from services.time_utils import build_time_metadata

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

@router.post("/v1/ai/cosmic-chat")
async def cosmic_chat(body: CosmicChatRequest, request: Request, auth=Depends(get_auth)):
    """Inicia um chat interpretativo com IA baseado em dados astrológicos."""
    request_id = getattr(request.state, "request_id", None) or str(uuid4())

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("cosmic_chat_not_configured", extra={"request_id": request_id})
        raise HTTPException(status_code=500, detail="Serviço de IA temporariamente indisponível.")

    try:
        client = OpenAI(api_key=api_key)
        messages = build_cosmic_chat_messages(
            user_question=body.user_question, astro_payload=body.astro_payload,
            tone=body.tone or "calmo, adulto, tecnológico", language=body.language or "pt-BR"
        )

        max_tokens = int(os.getenv("OPENAI_MAX_TOKENS_PAID", "1100")) if auth["plan"] != "free" else int(os.getenv("OPENAI_MAX_TOKENS_FREE", "600"))

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages, max_tokens=max_tokens, temperature=0.7
        )

        return {
            "response": response.choices[0].message.content,
            "usage": response.usage.model_dump(),
            "metadados_tecnicos": {
                "idioma": "pt-BR", "fonte_traducao": "backend",
                **build_time_metadata(None, None, None)
            }
        }
    except AuthenticationError:
        logger.exception("cosmic_chat_auth_error", extra={"request_id": request_id})
        return _build_ai_error_response(
            status_code=503,
            message="Serviço de IA temporariamente indisponível.",
            request_id=request_id,
            retryable=True,
        )
    except RateLimitError:
        logger.exception("cosmic_chat_quota_error", extra={"request_id": request_id})
        return _build_ai_error_response(
            status_code=429,
            message="Limite de uso da IA atingido. Tente novamente em instantes.",
            request_id=request_id,
            retryable=True,
        )
    except APITimeoutError:
        logger.exception("cosmic_chat_timeout", extra={"request_id": request_id})
        return _build_ai_error_response(
            status_code=504,
            message="Serviço de IA temporariamente indisponível.",
            request_id=request_id,
            retryable=True,
        )
    except (APIConnectionError, APIStatusError):
        logger.exception("cosmic_chat_external_api_error", extra={"request_id": request_id})
        return _build_ai_error_response(
            status_code=502,
            message="Serviço de IA temporariamente indisponível.",
            request_id=request_id,
            retryable=True,
        )
    except Exception:
        logger.exception("cosmic_chat_unhandled_error", extra={"request_id": request_id})
        return _build_ai_error_response(
            status_code=500,
            message="Serviço de IA temporariamente indisponível.",
            request_id=request_id,
            retryable=True,
        )
