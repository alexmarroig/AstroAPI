from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, AliasChoices, ConfigDict


class LunationCalculateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date: str = Field(..., description="YYYY-MM-DD", validation_alias=AliasChoices("date", "targetDate"))
    tz_offset_minutes: Optional[int] = Field(
        None,
        ge=-840,
        le=840,
        description="Minutos de offset para o fuso. Se vazio, usa timezone.",
        validation_alias=AliasChoices("tz_offset_minutes", "tzOffsetMinutes"),
    )
    timezone: Optional[str] = Field(
        None,
        description="Timezone IANA (ex.: America/Sao_Paulo). Se preenchido, substitui tz_offset_minutes",
    )
    strict_timezone: bool = Field(
        default=False,
        description="Quando true, rejeita horários ambíguos em transições de DST.",
        validation_alias=AliasChoices("strict_timezone", "strictTimezone"),
    )


class LunationCalculateResponse(BaseModel):
    date: str
    timezone: Optional[str]
    tz_offset_minutes: int
    phase_angle_deg: float
    phase: str
    phase_pt: str
    is_waxing: bool
    moon_sign: str
    moon_sign_pt: str
    sun_sign: str
    sun_sign_pt: str
    timezone_resolvida: Optional[str] = None
    tz_offset_minutes_usado: Optional[int] = None
    fold_usado: Optional[int] = None
    datetime_local_usado: Optional[str] = None
    datetime_utc_usado: Optional[str] = None
    avisos: Optional[list[str]] = None
