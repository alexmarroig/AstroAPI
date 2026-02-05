from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

MAX_USER_QUESTION_LENGTH = 1_200
MAX_ASTRO_PAYLOAD_DEPTH = 8
MAX_ASTRO_PAYLOAD_NODES = 1_500
MAX_ASTRO_PAYLOAD_STR_LENGTH = 2_000
MAX_ASTRO_PAYLOAD_CONTAINER_SIZE = 200


def _count_payload_nodes(value: Any, depth: int = 0) -> int:
    if depth > MAX_ASTRO_PAYLOAD_DEPTH:
        raise ValueError("astro_payload excede profundidade máxima suportada")

    if isinstance(value, str):
        if len(value) > MAX_ASTRO_PAYLOAD_STR_LENGTH:
            raise ValueError("astro_payload contém texto muito extenso")
        return 1

    if isinstance(value, dict):
        if len(value) > MAX_ASTRO_PAYLOAD_CONTAINER_SIZE:
            raise ValueError("astro_payload contém objeto com muitas chaves")
        total = 1
        for key, nested in value.items():
            total += _count_payload_nodes(str(key), depth + 1)
            total += _count_payload_nodes(nested, depth + 1)
            if total > MAX_ASTRO_PAYLOAD_NODES:
                raise ValueError("astro_payload excede tamanho máximo permitido")
        return total

    if isinstance(value, list):
        if len(value) > MAX_ASTRO_PAYLOAD_CONTAINER_SIZE:
            raise ValueError("astro_payload contém lista muito grande")
        total = 1
        for nested in value:
            total += _count_payload_nodes(nested, depth + 1)
            if total > MAX_ASTRO_PAYLOAD_NODES:
                raise ValueError("astro_payload excede tamanho máximo permitido")
        return total

    return 1


class CosmicChatRequest(BaseModel):
    """Modelo para requisição de chat cósmico (IA)."""

    user_question: str = Field(..., min_length=1, max_length=MAX_USER_QUESTION_LENGTH)
    astro_payload: Dict[str, Any] = Field(...)
    tone: Optional[str] = Field(default=None, max_length=120)
    language: str = Field(default="pt-BR", max_length=32)

    @field_validator("astro_payload")
    @classmethod
    def validate_astro_payload_size(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        _count_payload_nodes(value)
        return value
