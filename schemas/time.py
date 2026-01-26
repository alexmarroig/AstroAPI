from __future__ import annotations
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, model_validator

class TimezoneResolveRequest(BaseModel):
    """Modelo para requisição de resolução de timezone."""
    datetime_local: Optional[datetime] = Field(
        None, description="Compatibilidade: data/hora local ISO (ex.: 2025-12-19T14:30:00)"
    )
    year: int = Field(..., ge=1800, le=2100)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(0, ge=0, le=59)
    second: int = Field(0, ge=0, le=59)
    timezone: str = Field(..., description="Timezone IANA, ex.: America/Sao_Paulo")
    strict_birth: bool = Field(
        default=False,
        description="Quando true, acusa horários ambíguos em transições de DST para dados de nascimento.",
    )

    @model_validator(mode="before")
    @classmethod
    def reject_natal_aliases(cls, data: Any):
        if isinstance(data, dict) and any(key.startswith("natal_") for key in data.keys()):
            from fastapi import HTTPException
            raise HTTPException(
                status_code=422,
                detail="Use year/month/day/hour/minute/second for resolve-tz (not natal_*).",
            )
        return data

    @model_validator(mode="before")
    @classmethod
    def coerce_datetime_local(cls, data: Any):
        if not isinstance(data, dict):
            return data
        if data.get("datetime_local") and not all(
            key in data for key in ("year", "month", "day", "hour")
        ):
            dt = data["datetime_local"]
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt)
            data = {**data}
            data.setdefault("year", dt.year)
            data.setdefault("month", dt.month)
            data.setdefault("day", dt.day)
            data.setdefault("hour", dt.hour)
            data.setdefault("minute", dt.minute)
            data.setdefault("second", dt.second)
        return data

class ValidateLocalDatetimeRequest(BaseModel):
    """Modelo para validação de data/hora local."""
    datetime_local: datetime = Field(..., description="Data/hora local, ex.: 2024-11-03T01:30:00")
    timezone: str = Field(..., description="Timezone IANA, ex.: America/New_York")
    strict: bool = Field(
        default=True,
        description="Quando true, rejeita horário ambíguo/inexistente nas transições de DST.",
    )
    prefer_fold: int = Field(
        default=0,
        ge=0,
        le=1,
        description="Preferência de fold (0 ou 1) para horários ambíguos.",
    )
