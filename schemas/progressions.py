from __future__ import annotations

from typing import Optional

from enum import Enum

from pydantic import BaseModel, Field


class HouseSystem(str, Enum):
    PLACIDUS = "P"
    KOCH = "K"
    REGIOMONTANUS = "R"


class ZodiacType(str, Enum):
    TROPICAL = "tropical"
    SIDEREAL = "sidereal"


class SecondaryProgressionCalculateRequest(BaseModel):
    natal_year: int = Field(..., ge=1800, le=2100)
    natal_month: int = Field(..., ge=1, le=12)
    natal_day: int = Field(..., ge=1, le=31)
    natal_hour: int = Field(..., ge=0, le=23)
    natal_minute: int = Field(0, ge=0, le=59)
    natal_second: int = Field(0, ge=0, le=59)
    lat: float = Field(..., ge=-89.9999, le=89.9999)
    lng: float = Field(..., ge=-180, le=180)
    tz_offset_minutes: Optional[int] = Field(
        None, ge=-840, le=840, description="Minutos de offset para o fuso. Se vazio, usa timezone."
    )
    timezone: Optional[str] = Field(
        None,
        description="Timezone IANA (ex.: America/Sao_Paulo). Se preenchido, substitui tz_offset_minutes",
    )
    target_date: str = Field(..., description="YYYY-MM-DD")
    house_system: HouseSystem = Field(default=HouseSystem.PLACIDUS)
    zodiac_type: ZodiacType = Field(default=ZodiacType.TROPICAL)
    ayanamsa: Optional[str] = Field(
        default=None, description="Opcional para zodíaco sideral (ex.: lahiri, fagan_bradley)",
    )
    strict_timezone: bool = Field(
        default=False,
        description="Quando true, rejeita horários ambíguos em transições de DST.",
    )


class SecondaryProgressionCalculateResponse(BaseModel):
    natal_datetime_local: str
    target_date: str
    progressed_datetime_local: str
    age_years: float
    tz_offset_minutes: int
    chart: dict
    chart_ptbr: Optional[dict] = None
    timezone_resolvida: Optional[str] = None
    tz_offset_minutes_usado: Optional[int] = None
    fold_usado: Optional[int] = None
    datetime_local_usado: Optional[str] = None
    datetime_utc_usado: Optional[str] = None
    avisos: Optional[list[str]] = None
