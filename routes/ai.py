from __future__ import annotations
import os
import logging
from fastapi import APIRouter, Depends, Request, HTTPException
from openai import OpenAI

from .common import get_auth
from schemas.ai import CosmicChatRequest
from ai.prompts import build_cosmic_chat_messages
from services.time_utils import build_time_metadata

router = APIRouter()
logger = logging.getLogger("astro-api")

@router.post("/v1/ai/cosmic-chat")
async def cosmic_chat(body: CosmicChatRequest, request: Request, auth=Depends(get_auth)):
    """Inicia um chat interpretativo com IA baseado em dados astrológicos."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key: raise HTTPException(status_code=500, detail="IA não configurada.")

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
    except Exception as e:
        logger.error("cosmic_chat_error", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro na IA: {str(e)}")
