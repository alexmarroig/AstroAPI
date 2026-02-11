from __future__ import annotations

from typing import Optional, Any

from enum import Enum

from pydantic import BaseModel, Field, AliasChoices, model_validator, ConfigDict


class HouseSystem(str, Enum):
    PLACIDUS = "P"
    KOCH = "K"
    REGIOMONTANUS = "R"


class ZodiacType(str, Enum):
    TROPICAL = "tropical"
    SIDEREAL = "sidereal"


class SecondaryProgressionCalculateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    natal_year: int = Field(..., ge=1800, le=2100, validation_alias=AliasChoices("natal_year", "year"))
    natal_month: int = Field(..., ge=1, le=12, validation_alias=AliasChoices("natal_month", "month"))
    natal_day: int = Field(..., ge=1, le=31, validation_alias=AliasChoices("natal_day", "day"))
    natal_hour: int = Field(..., ge=0, le=23, validation_alias=AliasChoices("natal_hour", "hour"))
    natal_minute: int = Field(0, ge=0, le=59, validation_alias=AliasChoices("natal_minute", "minute"))
    natal_second: int = Field(0, ge=0, le=59, validation_alias=AliasChoices("natal_second", "second"))
    birth_date: Optional[str] = Field(default=None, validation_alias=AliasChoices("birth_date", "birthDate"))
    birth_time: Optional[str] = Field(default=None, validation_alias=AliasChoices("birth_time", "birthTime"))
    birth_datetime: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("birth_datetime", "birthDateTime", "birthDatetime"),
    )
    lat: float = Field(..., ge=-89.9999, le=89.9999)
    lng: float = Field(..., ge=-180, le=180)
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
    target_date: str = Field(..., description="YYYY-MM-DD", validation_alias=AliasChoices("target_date", "targetDate"))
    house_system: HouseSystem = Field(default=HouseSystem.PLACIDUS)
    zodiac_type: ZodiacType = Field(default=ZodiacType.TROPICAL)
    ayanamsa: Optional[str] = Field(
        default=None, description="Opcional para zodíaco sideral (ex.: lahiri, fagan_bradley)",
    )
    strict_timezone: bool = Field(
        default=False,
        description="Quando true, rejeita horários ambíguos em transições de DST.",
        validation_alias=AliasChoices("strict_timezone", "strictTimezone"),
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_birth_datetime(cls, data: Any):
        if not isinstance(data, dict):
            return data

        from services.time_utils import resolve_birth_datetime_payload

        dt, _, _ = resolve_birth_datetime_payload(data)
        if dt is None:
            return data

        data.setdefault("natal_year", dt.year)
        data.setdefault("natal_month", dt.month)
        data.setdefault("natal_day", dt.day)
        data.setdefault("natal_hour", dt.hour)
        data.setdefault("natal_minute", dt.minute)
        data.setdefault("natal_second", dt.second)
        return data


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
