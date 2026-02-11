from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel, Field, AliasChoices, model_validator, ConfigDict
from .common import HouseSystem, ZodiacType

class NatalChartRequest(BaseModel):
    """Modelo para requisição de mapa natal."""
    model_config = ConfigDict(populate_by_name=True)

    natal_year: int = Field(..., ge=1800, le=2100)
    natal_month: int = Field(..., ge=1, le=12)
    natal_day: int = Field(..., ge=1, le=31)
    natal_hour: int = Field(..., ge=0, le=23)
    natal_minute: int = Field(0, ge=0, le=59)
    natal_second: int = Field(0, ge=0, le=59)
    birth_date: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("birth_date", "birthDate"),
        description="Data de nascimento em YYYY-MM-DD (alternativo aos campos natal_*).",
    )
    birth_time: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("birth_time", "birthTime"),
        description="Hora de nascimento em HH:MM ou HH:MM:SS. Pode ser null se não souber a hora exata.",
    )
    birth_datetime: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("birth_datetime", "birthDateTime", "birthDatetime"),
        description="Data/hora de nascimento em ISO (ex.: 2026-01-01T20:54:00).",
    )
    birth_time_precise: Optional[bool] = Field(
        default=None,
        validation_alias=AliasChoices("birth_time_precise", "birthTimePrecise"),
        description="Indica se o horário de nascimento foi informado com precisão.",
    )
    year: int = Field(
        ...,
        ge=1800,
        le=2100,
        validation_alias=AliasChoices("year", "natal_year"),
        description="Ano de nascimento (aceita alias natal_year).",
    )
    month: int = Field(
        ...,
        ge=1,
        le=12,
        validation_alias=AliasChoices("month", "natal_month"),
        description="Mês de nascimento (aceita alias natal_month).",
    )
    day: int = Field(
        ...,
        ge=1,
        le=31,
        validation_alias=AliasChoices("day", "natal_day"),
        description="Dia de nascimento (aceita alias natal_day).",
    )
    hour: int = Field(
        ...,
        ge=0,
        le=23,
        validation_alias=AliasChoices("hour", "natal_hour"),
        description="Hora de nascimento (aceita alias natal_hour).",
    )
    minute: int = Field(
        0,
        ge=0,
        le=59,
        validation_alias=AliasChoices("minute", "natal_minute"),
        description="Minuto de nascimento (aceita alias natal_minute).",
    )
    second: int = Field(
        0,
        ge=0,
        le=59,
        validation_alias=AliasChoices("second", "natal_second"),
        description="Segundo de nascimento (aceita alias natal_second).",
    )
    lat: float = Field(..., ge=-89.9999, le=89.9999)
    lng: float = Field(..., ge=-180, le=180)
    tz_offset_minutes: Optional[int] = Field(
        None, ge=-840, le=840, description="Minutos de offset para o fuso. Se vazio, usa timezone."
    )
    timezone: Optional[str] = Field(
        None,
        description="Timezone IANA (ex.: America/Sao_Paulo). Se preenchido, substitui tz_offset_minutes",
    )
    house_system: HouseSystem = Field(default=HouseSystem.PLACIDUS)
    zodiac_type: ZodiacType = Field(default=ZodiacType.TROPICAL)
    ayanamsa: Optional[str] = Field(
        default=None, description="Opcional para zodíaco sideral (ex.: lahiri, fagan_bradley)",
    )
    strict_timezone: bool = Field(
        default=False,
        description="Quando true, rejeita horários ambíguos em transições de DST para evitar datas erradas.",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_birth_datetime(cls, data: Any):
        """Normaliza os diversos formatos de data/hora de nascimento para os campos padrão."""
        if not isinstance(data, dict):
            return data

        from services.time_utils import resolve_birth_datetime_payload
        dt, precise, _ = resolve_birth_datetime_payload(data)

        if dt is None:
            if "birth_time_precise" not in data and "birthTimePrecise" not in data:
                data["birth_time_precise"] = True
            return data

        # Define os campos natal_* e year/month/day/etc
        for prefix in ["natal_", ""]:
            data.setdefault(f"{prefix}year", dt.year)
            data.setdefault(f"{prefix}month", dt.month)
            data.setdefault(f"{prefix}day", dt.day)
            data.setdefault(f"{prefix}hour", dt.hour)
            data.setdefault(f"{prefix}minute", dt.minute)
            data.setdefault(f"{prefix}second", dt.second)

        data["birth_time_precise"] = precise
        return data

    @model_validator(mode="after")
    def validate_tz(self):
        if self.tz_offset_minutes is None and not self.timezone:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail="Informe timezone IANA ou tz_offset_minutes para calcular o mapa.",
            )
        return self

class RenderDataRequest(BaseModel):
    """Modelo para requisição de dados de renderização do mapa."""
    year: int
    month: int
    day: int
    hour: int
    minute: int = 0
    second: int = 0
    lat: float = Field(..., ge=-89.9999, le=89.9999)
    lng: float = Field(..., ge=-180, le=180)
    tz_offset_minutes: Optional[int] = Field(
        None, ge=-840, le=840, description="Minutos de offset para o fuso. Se vazio, usa timezone."
    )
    timezone: str = Field(
        ..., description="Timezone IANA (ex.: America/Sao_Paulo). Obrigatório para renderização."
    )
    house_system: HouseSystem = Field(default=HouseSystem.PLACIDUS)
    zodiac_type: ZodiacType = Field(default=ZodiacType.TROPICAL)
    ayanamsa: Optional[str] = Field(
        default=None, description="Opcional para zodíaco sideral (ex.: lahiri, fagan_bradley)",
    )
    strict_timezone: bool = Field(
        default=False,
        description="Quando true, rejeita horários ambíguos em transições de DST para evitar datas erradas.",
    )

    @model_validator(mode="after")
    def validate_tz(self):
        if not self.timezone:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="timezone is required")
        return self

    @model_validator(mode="before")
    @classmethod
    def reject_date_aliases(cls, data: Any):
        if isinstance(data, dict):
            from fastapi import HTTPException
            if not data.get("timezone"):
                raise HTTPException(status_code=422, detail="timezone is required")
            if any(key.startswith("natal_") for key in data.keys()):
                raise HTTPException(
                    status_code=422,
                    detail="render-data expects year/month/day/hour/minute/second...",
                )
        return data
