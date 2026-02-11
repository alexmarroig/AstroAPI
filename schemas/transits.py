from __future__ import annotations
from typing import Optional, Any, List, Dict, Literal
from pydantic import BaseModel, Field, AliasChoices, model_validator, ConfigDict
from .common import HouseSystem, ZodiacType, PreferenciasPerfil

class TransitsRequest(BaseModel):
    """Modelo para requisição de trânsitos."""
    model_config = ConfigDict(populate_by_name=True)
    natal_year: int = Field(
        ...,
        ge=1800,
        le=2100,
        validation_alias=AliasChoices("natal_year", "year"),
        description="Ano de nascimento (aceita alias year).",
    )
    natal_month: int = Field(
        ...,
        ge=1,
        le=12,
        validation_alias=AliasChoices("natal_month", "month"),
        description="Mês de nascimento (aceita alias month).",
    )
    natal_day: int = Field(
        ...,
        ge=1,
        le=31,
        validation_alias=AliasChoices("natal_day", "day"),
        description="Dia de nascimento (aceita alias day).",
    )
    natal_hour: int = Field(
        ...,
        ge=0,
        le=23,
        validation_alias=AliasChoices("natal_hour", "hour"),
        description="Hora de nascimento (aceita alias hour).",
    )
    natal_minute: int = Field(
        0,
        ge=0,
        le=59,
        validation_alias=AliasChoices("natal_minute", "minute"),
        description="Minuto de nascimento (aceita alias minute).",
    )
    natal_second: int = Field(
        0,
        ge=0,
        le=59,
        validation_alias=AliasChoices("natal_second", "second"),
        description="Segundo de nascimento (aceita alias second).",
    )
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
    aspectos_habilitados: Optional[List[str]] = Field(
        default=None,
        description="Lista de aspectos habilitados (ex.: ['conj', 'opos', 'quad', 'tri', 'sext']).",
    )
    orbes: Optional[Dict[str, float]] = Field(
        default=None,
        description="Orbes por aspecto, ex.: {'conj': 8, 'opos': 6}.",
    )
    strict_timezone: bool = Field(
        default=False,
        description="Quando true, rejeita horários ambíguos em transições de DST para evitar datas erradas.",
    )
    preferencias: Optional[PreferenciasPerfil] = None

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

        data.setdefault("natal_year", dt.year)
        data.setdefault("natal_month", dt.month)
        data.setdefault("natal_day", dt.day)
        data.setdefault("natal_hour", dt.hour)
        data.setdefault("natal_minute", dt.minute)
        data.setdefault("natal_second", dt.second)

        data["birth_time_precise"] = precise
        return data

    @model_validator(mode="after")
    def validate_tz(self):
        if self.tz_offset_minutes is None and not self.timezone:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail="Informe timezone IANA ou tz_offset_minutes para calcular trânsitos.",
            )
        return self

    @model_validator(mode="before")
    @classmethod
    def reject_date_aliases(cls, data: Any):
        if isinstance(data, dict):
            from fastapi import HTTPException
            has_year_fields = any(key in data for key in ("year", "month", "day", "hour"))
            has_natal_fields = any(key.startswith("natal_") for key in data.keys())
            if has_year_fields and not has_natal_fields:
                raise HTTPException(
                    status_code=422,
                    detail="Use natal_year/natal_month/natal_day/natal_hour... for transits.",
                )
        return data

class TransitsLiveRequest(BaseModel):
    """Modelo para requisição de trânsitos em tempo real (live)."""
    target_datetime: Any = Field(..., description="Data/hora alvo com timezone (ISO 8601).")
    tz_offset_minutes: Optional[int] = Field(
        None, ge=-840, le=840, description="Offset manual em minutos; opcional se timezone for enviado."
    )
    timezone: Optional[str] = Field(
        None,
        description="Timezone IANA (ex.: America/Sao_Paulo). Se preenchido, substitui tz_offset_minutes",
    )
    strict_timezone: bool = Field(
        default=False,
        description="Quando true, rejeita horários ambíguos em transições de DST para evitar datas erradas.",
    )
    lat: float = Field(..., ge=-89.9999, le=89.9999)
    lng: float = Field(..., ge=-180, le=180)
    zodiac_type: ZodiacType = Field(default=ZodiacType.TROPICAL)
    ayanamsa: Optional[str] = Field(
        default=None, description="Opcional para zodíaco sideral (ex.: lahiri, fagan_bradley)",
    )

class TransitDateRange(BaseModel):
    """Modelo para intervalo de datas de trânsitos."""
    from_: str = Field(..., alias="from", description="Data inicial YYYY-MM-DD.")
    to: str = Field(..., description="Data final YYYY-MM-DD.")

class TransitsEventsRequest(TransitsRequest):
    """Modelo para requisição de eventos de trânsito em um intervalo."""
    target_date: Optional[str] = Field(
        default=None, description="Campo opcional (ignorado quando range é fornecido)."
    )
    range: TransitDateRange
    preferencias: Optional[PreferenciasPerfil] = None

class TransitEventDateRange(BaseModel):
    """Modelo para o intervalo de tempo de um evento de trânsito."""
    start_utc: str
    peak_utc: str
    end_utc: str

class TransitEventCopy(BaseModel):
    """Modelo para os textos explicativos de um evento de trânsito."""
    headline: str
    mecanica: str
    use_bem: str
    risco: str

class TransitEvent(BaseModel):
    """Modelo para um evento de trânsito individual."""
    event_id: str
    date_range: TransitEventDateRange
    transitando: str
    alvo_tipo: Literal["PLANETA_NATAL", "ANGULO_NATAL", "CUSPIDE_CASA_NATAL"]
    alvo: str
    aspecto: str
    orb_graus: float
    casa_ativada: Optional[int] = None
    tags: List[str]
    severidade: Literal["BAIXA", "MEDIA", "ALTA"]
    impact_score: float
    copy: TransitEventCopy

class TransitEventsResponse(BaseModel):
    """Resposta para a listagem de eventos de trânsito."""
    events: List[TransitEvent]
    metadados: Dict[str, Any]
    avisos: List[str]
