from __future__ import annotations
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class CosmicChatRequest(BaseModel):
    """Modelo para requisição de chat cósmico (IA)."""
    user_question: str = Field(..., min_length=1)
    astro_payload: Dict[str, Any] = Field(...)
    tone: Optional[str] = None
    language: str = Field("pt-BR")
