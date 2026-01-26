from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from .common import ZodiacType

class MercuryRetrogradeRequest(BaseModel):
    """Modelo para requisição de insight de Mercúrio retrógrado."""
    target_date: str = Field(..., description="YYYY-MM-DD")
    lat: float = Field(..., ge=-89.9999, le=89.9999)
    lng: float = Field(..., ge=-180, le=180)
    tz_offset_minutes: Optional[int] = Field(
        None, ge=-840, le=840, description="Minutos de offset para o fuso. Se vazio, usa timezone."
    )
    timezone: Optional[str] = Field(
        None,
        description="Timezone IANA (ex.: America/Sao_Paulo). Se preenchido, substitui tz_offset_minutes",
    )
    zodiac_type: ZodiacType = Field(default=ZodiacType.TROPICAL)
    ayanamsa: Optional[str] = Field(
        default=None, description="Opcional para zodíaco sideral (ex.: lahiri, fagan_bradley)",
    )

    @model_validator(mode="after")
    def validate_tz(self):
        if self.tz_offset_minutes is None and not self.timezone:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail="Informe timezone IANA ou tz_offset_minutes para calcular retrogradação.",
            )
        return self
