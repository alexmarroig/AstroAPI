from __future__ import annotations
from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field

class HouseSystem(str, Enum):
    """Sistemas de casas suportados."""
    PLACIDUS = "P"
    KOCH = "K"
    REGIOMONTANUS = "R"

class ZodiacType(str, Enum):
    """Tipos de zodíaco suportados."""
    TROPICAL = "tropical"
    SIDEREAL = "sidereal"

class PreferenciasPerfil(BaseModel):
    """Preferências de perfil do usuário para cálculos."""
    perfil: Optional[Literal["padrao", "custom"]] = Field(
        default=None, description="Perfil de preferências: padrao ou custom."
    )
    orb_max_deg: Optional[float] = Field(
        default=None, ge=0, description="Orb máximo para scoring quando em perfil custom."
    )
