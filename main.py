import os
import time
import uuid
import json
import hashlib
from dataclasses import replace
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Any, Dict, Literal, List
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.timezone_utils import TimezoneResolutionError, resolve_timezone_offset

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict, model_validator, AliasChoices
from fastapi.exceptions import RequestValidationError
from openai import OpenAI
import swisseph as swe

from astro.ephemeris import PLANETS, compute_chart, compute_transits, compute_moon_only, solar_return_datetime
from astro.ephemeris import PLANETS, compute_chart, compute_transits, compute_moon_only
from astro.solar_return import SolarReturnInputs, compute_solar_return_payload
from astro.aspects import compute_transit_aspects, get_aspects_profile, resolve_aspects_config
from astro.retrogrades import retrograde_alerts
from astro.i18n_ptbr import (
    aspect_to_ptbr,
    build_aspects_ptbr,
    build_houses_ptbr,
    build_planets_ptbr,
    format_degree_ptbr,
    format_position_ptbr,
    planet_key_to_ptbr,
    sign_to_ptbr,
    sign_for_longitude,
)
from astro.utils import angle_diff, to_julian_day, sign_to_pt, ZODIAC_SIGNS, ZODIAC_SIGNS_PT
from ai.prompts import build_cosmic_chat_messages
from services.time_utils import localize_with_zoneinfo, parse_local_datetime, to_utc
from timezone_utils import parse_local_datetime as parse_local_datetime_ptbr

from core.security import require_api_key_and_user
from core.cache import cache
from core.plans import TRIAL_SECONDS, get_user_plan, is_trial_or_premium
from services.timezone_utils import resolve_local_datetime
from routes.lunations import router as lunations_router
from routes.progressions import router as progressions_router
from services import timezone_utils

# -----------------------------
# Load env
# -----------------------------
load_dotenv()
SOLAR_RETURN_ENGINE = os.getenv("SOLAR_RETURN_ENGINE", "v1").lower()

# -----------------------------
# Logging (structured)
# -----------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("astro-api")
logger.setLevel(LOG_LEVEL)
handler = logging.StreamHandler()
handler.setLevel(LOG_LEVEL)
logger.propagate = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "ts": datetime.utcnow().isoformat() + "Z",
            "msg": record.getMessage(),
        }
        standard = {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
        }
        for key, value in record.__dict__.items():
            if key in standard or key in payload:
                continue
            try:
                json.dumps(value, ensure_ascii=False)
                payload[key] = value
            except TypeError:
                payload[key] = str(value)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


handler.setFormatter(JsonFormatter())
logger.handlers = [handler]


def _log(level: str, message: str, **extra: Any) -> None:
    """Small wrapper to keep structured logging consistent."""
    log_method = getattr(logger, level)
    log_method(message, extra=extra)

# -----------------------------
# App
# -----------------------------
app = FastAPI(
    title="Premium Astrology API",
    description="Accurate astrological calculations using Swiss Ephemeris with AI-powered cosmic insights",
    version="1.1.1",
)

# -----------------------------
# CORS
# -----------------------------
origins = os.getenv("ALLOWED_ORIGINS", "*")
allowed = [o.strip() for o in origins.split(",")] if origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # Authorization + X-User-Id
)

# -----------------------------
# Routers (isolated services)
# -----------------------------
app.include_router(lunations_router)
app.include_router(progressions_router)

# -----------------------------
# Middleware: request_id + logging
# -----------------------------
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id

    start = time.time()
    try:
        response = await call_next(request)
        latency_ms = int((time.time() - start) * 1000)

        extra = {
            "request_id": request_id,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": latency_ms,
        }
        _log("info", "request", **extra)
        if request.url.path == "/v1/chart/render-data":
            auth_present = bool(request.headers.get("authorization"))
            user_id_header = request.headers.get("x-user-id")
            _log(
                "info",
                f"render_data_proxy headers auth_present={auth_present} x_user_id_present={bool(user_id_header)}",
                request_id=request_id,
                path=request.url.path,
                status=response.status_code,
                latency_ms=latency_ms,
                user_id=user_id_header,
            )

        response.headers["X-Request-Id"] = request_id
        return response

    except Exception:
        latency_ms = int((time.time() - start) * 1000)
        extra = {
            "request_id": request_id,
            "path": request.url.path,
            "status": 500,
            "latency_ms": latency_ms,
        }
        logger.error("unhandled_exception", exc_info=True, extra=extra)
        return JSONResponse(
            status_code=500,
            content={
                "error": "SERVIDOR_TEMPORARIO",
                "message": "Tente novamente em 1 minuto",
                "request_id": request_id,
            },
            headers={"X-Request-Id": request_id},
        )

# -----------------------------
# Exception handler: HTTPException
# -----------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    extra = {
        "request_id": request_id,
        "path": request.url.path,
        "status": exc.status_code,
        "latency_ms": None,
    }
    _log("warning", "http_exception", **extra)
    payload = {
        "detail": exc.detail,
        "request_id": request_id,
        "code": f"http_{exc.status_code}",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=payload,
        headers={"X-Request-Id": request_id},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    extra = {
        "request_id": request_id,
        "path": request.url.path,
        "status": 422,
        "latency_ms": None,
    }
    _log("warning", "validation_error", **extra)
    payload = {
        "detail": exc.errors(),
        "request_id": request_id,
        "code": "validation_error",
    }
    return JSONResponse(status_code=422, content=payload, headers={"X-Request-Id": request_id})

# -----------------------------
# Auth dependency
# -----------------------------
def get_auth(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None),
):
    auth = require_api_key_and_user(
        authorization=authorization,
        x_user_id=x_user_id,
        request_path=request.url.path,
    )
    return auth

# -----------------------------
# Models
# -----------------------------
class HouseSystem(str, Enum):
    PLACIDUS = "P"
    KOCH = "K"
    REGIOMONTANUS = "R"


class ZodiacType(str, Enum):
    TROPICAL = "tropical"
    SIDEREAL = "sidereal"


class PreferenciasPerfil(BaseModel):
    perfil: Optional[Literal["padrao", "custom"]] = Field(
        default=None, description="Perfil de preferências: padrao ou custom."
    )
    orb_max_deg: Optional[float] = Field(
        default=None, ge=0, description="Orb máximo para scoring quando em perfil custom."
    )


class NatalChartRequest(BaseModel):
    natal_year: int = Field(..., ge=1800, le=2100)
    natal_month: int = Field(..., ge=1, le=12)
    natal_day: int = Field(..., ge=1, le=31)
    natal_hour: int = Field(..., ge=0, le=23)
    natal_minute: int = Field(0, ge=0, le=59)
    natal_second: int = Field(0, ge=0, le=59)
    birth_date: Optional[str] = Field(
        default=None,
        description="Data de nascimento em YYYY-MM-DD (alternativo aos campos natal_*).",
    )
    birth_time: Optional[str] = Field(
        default=None,
        description="Hora de nascimento em HH:MM ou HH:MM:SS. Pode ser null se não souber a hora exata.",
    )
    birth_datetime: Optional[str] = Field(
        default=None,
        description="Data/hora de nascimento em ISO (ex.: 2026-01-01T20:54:00).",
    )
    birth_time_precise: Optional[bool] = Field(
        default=None,
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
        if not isinstance(data, dict):
            return data
        dt, precise, warnings = _resolve_birth_datetime_payload(data)
        if dt is None:
            if "birth_time_precise" not in data:
                data["birth_time_precise"] = True
            return data
        data.setdefault("natal_year", dt.year)
        data.setdefault("natal_month", dt.month)
        data.setdefault("natal_day", dt.day)
        data.setdefault("natal_hour", dt.hour)
        data.setdefault("natal_minute", dt.minute)
        data.setdefault("natal_second", dt.second)
        data.setdefault("year", dt.year)
        data.setdefault("month", dt.month)
        data.setdefault("day", dt.day)
        data.setdefault("hour", dt.hour)
        data.setdefault("minute", dt.minute)
        data.setdefault("second", dt.second)
        data["birth_time_precise"] = precise
        return data

    @model_validator(mode="after")
    def validate_tz(self):
        if self.tz_offset_minutes is None and not self.timezone:
            raise HTTPException(
                status_code=400,
                detail="Informe timezone IANA ou tz_offset_minutes para calcular o mapa.",
            )
        return self

class TransitsRequest(BaseModel):
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
        description="Data de nascimento em YYYY-MM-DD (alternativo aos campos natal_*).",
    )
    birth_time: Optional[str] = Field(
        default=None,
        description="Hora de nascimento em HH:MM ou HH:MM:SS. Pode ser null se não souber a hora exata.",
    )
    birth_datetime: Optional[str] = Field(
        default=None,
        description="Data/hora de nascimento em ISO (ex.: 2026-01-01T20:54:00).",
    )
    birth_time_precise: Optional[bool] = Field(
        default=None,
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
        if not isinstance(data, dict):
            return data
        dt, precise, warnings = _resolve_birth_datetime_payload(data)
        if dt is None:
            if "birth_time_precise" not in data:
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
            raise HTTPException(
                status_code=400,
                detail="Informe timezone IANA ou tz_offset_minutes para calcular trânsitos.",
            )
        return self

    @model_validator(mode="before")
    @classmethod
    def reject_date_aliases(cls, data: Any):
        if isinstance(data, dict):
            has_year_fields = any(key in data for key in ("year", "month", "day", "hour"))
            has_natal_fields = any(key.startswith("natal_") for key in data.keys())
            if has_year_fields and not has_natal_fields:
                raise HTTPException(
                    status_code=422,
                    detail="Use natal_year/natal_month/natal_day/natal_hour... for transits.",
                )
        return data

class TransitsLiveRequest(BaseModel):
    target_datetime: datetime = Field(..., description="Data/hora alvo com timezone (ISO 8601).")
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


class SynastryPerson(BaseModel):
    name: Optional[str] = None
    birth_date: str = Field(..., description="Data de nascimento YYYY-MM-DD.")
    birth_time: Optional[str] = Field(
        None, description="Hora de nascimento HH:MM ou HH:MM:SS (opcional)."
    )
    timezone: Optional[str] = Field(
        None, description="Timezone IANA (ex.: America/Sao_Paulo)."
    )
    tz_offset_minutes: Optional[int] = Field(
        None, ge=-840, le=840, description="Offset manual em minutos; opcional."
    )
    lat: float = Field(..., ge=-89.9999, le=89.9999)
    lng: float = Field(..., ge=-180, le=180)
    house_system: HouseSystem = Field(default=HouseSystem.PLACIDUS)
    zodiac_type: ZodiacType = Field(default=ZodiacType.TROPICAL)
    ayanamsa: Optional[str] = Field(default=None)


class SynastryRequest(BaseModel):
    person_a: SynastryPerson
    person_b: SynastryPerson

class SolarReturnRequest(BaseModel):
    natal_year: int = Field(..., ge=1800, le=2100)
    natal_month: int = Field(..., ge=1, le=12)
    natal_day: int = Field(..., ge=1, le=31)
    natal_hour: int = Field(..., ge=0, le=23)
    natal_minute: int = Field(0, ge=0, le=59)
    natal_second: int = Field(0, ge=0, le=59)
    target_year: int = Field(..., ge=1800, le=2100, description="Ano do retorno solar desejado.")
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

    @model_validator(mode="after")
    def validate_tz(self):
        if self.tz_offset_minutes is None and not self.timezone:
            raise HTTPException(
                status_code=400,
                detail="Informe timezone IANA ou tz_offset_minutes para calcular retorno solar.",
            )
        return self

class CosmicChatRequest(BaseModel):
    user_question: str = Field(..., min_length=1)
    astro_payload: Dict[str, Any] = Field(...)
    tone: Optional[str] = None
    language: str = Field("pt-BR")

class CosmicWeatherResponse(BaseModel):
    date: str
    moon_phase: str
    moon_sign: str
    moon_sign_pt: Optional[str] = None
    deg_in_sign: Optional[float] = None
    headline: str
    text: str
    moon_phase_ptbr: Optional[str] = None
    moon_sign_ptbr: Optional[str] = None
    headline_ptbr: Optional[str] = None
    text_ptbr: Optional[str] = None
    resumo_ptbr: Optional[str] = None
    moon_ptbr: Optional[Dict[str, Any]] = None
    top_event: Optional["TransitEvent"] = None
    trigger_event: Optional["TransitEvent"] = None
    secondary_events: Optional[List["TransitEvent"]] = None
    summary: Optional[Dict[str, str]] = None
    metadados_tecnicos: Optional[Dict[str, Any]] = None


class CosmicWeatherRangeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    items: List[CosmicWeatherResponse]
    items_ptbr: Optional[List[Dict[str, Any]]] = None

class RenderDataRequest(BaseModel):
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
            raise HTTPException(status_code=422, detail="timezone is required")
        return self

    @model_validator(mode="before")
    @classmethod
    def reject_date_aliases(cls, data: Any):
        if isinstance(data, dict):
            if not data.get("timezone"):
                raise HTTPException(status_code=422, detail="timezone is required")
            if any(key.startswith("natal_") for key in data.keys()):
                raise HTTPException(
                    status_code=422,
                    detail="render-data expects year/month/day/hour/minute/second...",
                )
        return data


class SolarReturnLocal(BaseModel):
    nome: Optional[str] = None
    lat: float = Field(..., ge=-89.9999, le=89.9999)
    lon: float = Field(..., ge=-180, le=180)
    alt_m: Optional[float] = None


class SolarReturnNatal(BaseModel):
    data: str = Field(..., description="Data natal no formato YYYY-MM-DD")
    hora: Optional[str] = Field(None, description="Hora natal no formato HH:MM:SS")
    timezone: str = Field(..., description="Timezone IANA (ex.: America/Sao_Paulo)")
    local: SolarReturnLocal


class SolarReturnTarget(BaseModel):
    ano: int = Field(..., ge=1800, le=2200)
    local: SolarReturnLocal
    timezone: Optional[str] = Field(
        None, description="Timezone IANA do local alvo (ex.: America/Sao_Paulo)."
    )


class SolarReturnPreferencias(BaseModel):
    perfil: Optional[Literal["padrao", "custom"]] = Field(
        default=None, description="Perfil de preferências (padrao/custom)."
    )
    zodiaco: ZodiacType = Field(default=ZodiacType.TROPICAL)
    ayanamsa: Optional[str] = None
    sistema_casas: HouseSystem = Field(default=HouseSystem.PLACIDUS)
    modo: Optional[Literal["geocentrico", "topocentrico"]] = Field(default="geocentrico")
    aspectos_habilitados: Optional[List[str]] = None
    orbes: Optional[Dict[str, float]] = None
    orb_max_deg: Optional[float] = Field(
        default=None, ge=0, description="Orb máximo para scoring quando em perfil custom."
    )
    janela_dias: Optional[int] = Field(
        default=None, ge=1, description="Janela em dias para busca do retorno solar."
    )
    passo_horas: Optional[int] = Field(
        default=None, ge=1, description="Passo em horas para busca do retorno solar."
    )
    max_iteracoes: Optional[int] = Field(
        default=None, ge=1, description="Iterações máximas no refinamento do retorno solar."
    )
    tolerancia_graus: Optional[float] = Field(
        default=None, gt=0, description="Tolerância em graus para refinamento do retorno solar."
    )


class SolarReturnRequest(BaseModel):
    natal: SolarReturnNatal
    alvo: SolarReturnTarget
    preferencias: Optional[SolarReturnPreferencias] = None


class TransitDateRange(BaseModel):
    from_: str = Field(..., alias="from", description="Data inicial YYYY-MM-DD.")
    to: str = Field(..., description="Data final YYYY-MM-DD.")


class TransitsEventsRequest(TransitsRequest):
    target_date: Optional[str] = Field(
        default=None, description="Campo opcional (ignorado quando range é fornecido)."
    )
    range: TransitDateRange
    preferencias: Optional[PreferenciasPerfil] = None


class TransitEventDateRange(BaseModel):
    start_utc: str
    peak_utc: str
    end_utc: str


class TransitEventCopy(BaseModel):
    headline: str
    mecanica: str
    use_bem: str
    risco: str


class TransitEvent(BaseModel):
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
    events: List[TransitEvent]
    metadados: Dict[str, Any]
    avisos: List[str]


class SolarReturnOverlayReference(BaseModel):
    solar_return_utc: Optional[str] = Field(default=None, description="UTC ISO já calculado.")
    year: Optional[int] = Field(default=None, ge=1800, le=2200)

    @model_validator(mode="after")
    def validate_reference(self):
        if not self.solar_return_utc and not self.year:
            raise HTTPException(status_code=422, detail="Informe solar_return_utc ou year.")
        return self


class SolarReturnOverlayRequest(BaseModel):
    natal: SolarReturnNatal
    alvo: SolarReturnTarget
    rs: Optional[SolarReturnOverlayReference] = None
    preferencias: Optional[SolarReturnPreferencias] = None


class SolarReturnTimelineRequest(BaseModel):
    natal: SolarReturnNatal
    year: int = Field(..., ge=1800, le=2200)
    preferencias: Optional[SolarReturnPreferencias] = None


class TimezoneResolveRequest(BaseModel):
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


class EphemerisCheckRequest(BaseModel):
    datetime_local: datetime = Field(..., description="Data/hora local, ex.: 2024-01-01T12:00:00")
    timezone: str = Field(..., description="Timezone IANA, ex.: Etc/UTC")
    lat: float = Field(..., ge=-89.9999, le=89.9999)
    lng: float = Field(..., ge=-180, le=180)


class MercuryRetrogradeRequest(BaseModel):
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
            raise HTTPException(
                status_code=400,
                detail="Informe timezone IANA ou tz_offset_minutes para calcular retrogradação.",
            )
        return self
class EphemerisCheckRequest(BaseModel):
    datetime_local: datetime = Field(..., description="Data/hora local, ex.: 2024-01-01T12:00:00")
    timezone: str = Field(..., description="Timezone IANA, ex.: Etc/UTC")
    lat: float = Field(..., ge=-89.9999, le=89.9999)
    lng: float = Field(..., ge=-180, le=180)


class SystemAlert(BaseModel):
    id: str
    severity: Literal["low", "medium", "high"]
    title: str
    body: str
    technical: Dict[str, Any] = Field(default_factory=dict)
    severity_ptbr: Optional[str] = None
    title_ptbr: Optional[str] = None
    body_ptbr: Optional[str] = None


class SystemAlertsResponse(BaseModel):
    date: str
    alerts: List[SystemAlert]
    alertas_ptbr: Optional[List[Dict[str, Any]]] = None
    tipos_ptbr: Optional[Dict[str, str]] = None


class NotificationsDailyResponse(BaseModel):
    date: str
    items: List[Dict[str, Any]]
    items_ptbr: Optional[List[Dict[str, Any]]] = None


class SolarReturnResponse(BaseModel):
    target_year: int
    solar_return_utc: str
    solar_return_local: str
    timezone_resolvida: Optional[str] = None
    tz_offset_minutes_usado: Optional[int] = None
    fold_usado: Optional[int] = None
    datetime_local_usado: Optional[str] = None
    datetime_utc_usado: Optional[str] = None
    avisos: Optional[List[str]] = None
    idioma: Optional[str] = None
    fonte_traducao: Optional[str] = None

# -----------------------------
# Helpers
# -----------------------------
def _parse_date_yyyy_mm_dd(s: str) -> tuple[int, int, int]:
    try:
        parsed = datetime.strptime(s, "%Y-%m-%d")
        return parsed.year, parsed.month, parsed.day
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato inválido de data. Use YYYY-MM-DD.")

def _parse_time_hh_mm_ss(s: str) -> tuple[int, int, int]:
    if not s:
        raise HTTPException(
            status_code=400,
            detail={"error": "HORA_INVALIDA", "message": "Hora inválida. Use HH:MM ou HH:MM:SS."},
        )
    try:
        if len(s) == 5:
            parsed = datetime.strptime(s, "%H:%M")
            return parsed.hour, parsed.minute, 0
        parsed = datetime.strptime(s, "%H:%M:%S")
        return parsed.hour, parsed.minute, parsed.second
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": "HORA_INVALIDA", "message": "Hora inválida. Use HH:MM ou HH:MM:SS."},
        )

def _resolve_birth_datetime_payload(data: Dict[str, Any]) -> tuple[Optional[datetime], Optional[bool], List[str]]:
    warnings: List[str] = []
    birth_datetime = data.get("birth_datetime")
    birth_date = data.get("birth_date")
    birth_time = data.get("birth_time")

    if birth_datetime:
        birth_datetime = str(birth_datetime).strip()
        time_included = "T" in birth_datetime
        try:
            if time_included:
                parsed = datetime.fromisoformat(birth_datetime)
            else:
                parsed = datetime.strptime(birth_datetime, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"error": "DATA_INVALIDA", "message": "Data inválida. Use YYYY-MM-DD ou ISO completo."},
            )
        if parsed.tzinfo:
            parsed = parsed.replace(tzinfo=None)
        if not time_included:
            parsed = parsed.replace(hour=12, minute=0, second=0)
            warnings.append("Hora não informada; usando 12:00 como referência.")
            return parsed, False, warnings
        return parsed, True, warnings

    if birth_date:
        birth_date = str(birth_date).strip()
        try:
            y, m, d = _parse_date_yyyy_mm_dd(birth_date)
        except HTTPException:
            raise HTTPException(
                status_code=400,
                detail={"error": "DATA_INVALIDA", "message": "Data inválida. Use YYYY-MM-DD."},
            )
        if birth_time:
            h, minute, second = _parse_time_hh_mm_ss(str(birth_time).strip())
            return datetime(year=y, month=m, day=d, hour=h, minute=minute, second=second), True, warnings
        warnings.append("Hora não informada; usando 12:00 como referência.")
        return datetime(year=y, month=m, day=d, hour=12, minute=0, second=0), False, warnings

    return None, None, warnings

def _moon_phase_4(phase_angle_deg: float) -> str:
    a = phase_angle_deg % 360
    if a < 45 or a >= 315:
        return "new_moon"
    if 45 <= a < 135:
        return "waxing"
    if 135 <= a < 225:
        return "full_moon"
    return "waning"

def _moon_phase_label_pt(phase: str) -> str:
    labels = {
        "new_moon": "Nova",
        "waxing": "Crescente",
        "full_moon": "Cheia",
        "waning": "Minguante",
    }
    return labels.get(phase, phase)

def _cw_text(phase: str, sign: str) -> str:
    options = [
        "O dia tende a favorecer mais presença emocional e escolhas com calma. Ajustes pequenos podem ter efeito grande.",
        "Pode ser um dia de observação interna. Priorize o essencial e evite decidir no pico da emoção.",
        "A energia pode ficar mais intensa em alguns momentos. Pausas curtas e ritmo consistente ajudam.",
    ]
    return options[hash(phase + sign) % len(options)]

def _is_pt_br(lang: Optional[str]) -> bool:
    return (lang or "").lower().replace("_", "-") == "pt-br"

def _apply_sign_localization(chart: Dict[str, Any], lang: Optional[str]) -> Dict[str, Any]:
    planets = chart.get("planets", {})
    for planet in planets.values():
        sign = planet.get("sign")
        if not sign:
            continue
        sign_pt = sign_to_pt(sign)
        planet["sign_pt"] = sign_pt
        if _is_pt_br(lang):
            planet["sign"] = sign_pt
    return chart

def _apply_moon_localization(payload: Dict[str, Any], lang: Optional[str]) -> Dict[str, Any]:
    sign = payload.get("moon_sign")
    if sign:
        sign_pt = sign_to_pt(sign)
        payload["moon_sign_pt"] = sign_pt
        if _is_pt_br(lang):
            payload["moon_sign"] = sign_pt
            if "headline" in payload:
                payload["headline"] = payload["headline"].replace(sign, sign_pt)
    return payload


def _build_chart_ptbr(chart: Dict[str, Any]) -> Dict[str, Any]:
    planets = chart.get("planets", {})
    houses = chart.get("houses", {})
    return {
        "planetas_ptbr": build_planets_ptbr(planets),
        "casas_ptbr": build_houses_ptbr(houses),
    }


def _build_cosmic_weather_ptbr(payload: Dict[str, Any]) -> Dict[str, Any]:
    moon_sign = payload.get("moon_sign", "")
    phase = payload.get("moon_phase", "")
    phase_label = _moon_phase_label_pt(phase) if phase else ""
    deg_in_sign = payload.get("deg_in_sign")
    return {
        "moon_phase_ptbr": phase_label,
        "moon_sign_ptbr": sign_to_ptbr(moon_sign),
        "headline_ptbr": payload.get("headline", ""),
        "text_ptbr": payload.get("text", ""),
        "moon_ptbr": {
            "signo_ptbr": sign_to_ptbr(moon_sign),
            "fase_ptbr": phase_label,
            "grau_formatado_ptbr": format_degree_ptbr(float(deg_in_sign))
            if deg_in_sign is not None
            else None,
        },
    }


ELEMENT_MAP = {
    "Aries": "Fogo",
    "Leo": "Fogo",
    "Sagittarius": "Fogo",
    "Taurus": "Terra",
    "Virgo": "Terra",
    "Capricorn": "Terra",
    "Gemini": "Ar",
    "Libra": "Ar",
    "Aquarius": "Ar",
    "Cancer": "Água",
    "Scorpio": "Água",
    "Pisces": "Água",
}

MODALITY_MAP = {
    "Aries": "Cardinal",
    "Cancer": "Cardinal",
    "Libra": "Cardinal",
    "Capricorn": "Cardinal",
    "Taurus": "Fixo",
    "Leo": "Fixo",
    "Scorpio": "Fixo",
    "Aquarius": "Fixo",
    "Gemini": "Mutável",
    "Virgo": "Mutável",
    "Sagittarius": "Mutável",
    "Pisces": "Mutável",
}

RULER_MAP = {
    "Aries": "Mars",
    "Taurus": "Venus",
    "Gemini": "Mercury",
    "Cancer": "Moon",
    "Leo": "Sun",
    "Virgo": "Mercury",
    "Libra": "Venus",
    "Scorpio": "Mars",
    "Sagittarius": "Jupiter",
    "Capricorn": "Saturn",
    "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}


def _house_for_lon(cusps: List[float], lon: float) -> int:
    if not cusps:
        return 1
    lon_mod = lon % 360
    for idx in range(12):
        start = float(cusps[idx])
        end = float(cusps[(idx + 1) % 12])
        start_mod = start
        end_mod = end
        lon_check = lon_mod
        if end_mod < start_mod:
            end_mod += 360
            if lon_check < start_mod:
                lon_check += 360
        if start_mod <= lon_check < end_mod:
            return idx + 1
    return 12


def _distributions_payload(
    chart: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    elements = {"Fogo": 0, "Terra": 0, "Ar": 0, "Água": 0}
    modalities = {"Cardinal": 0, "Fixo": 0, "Mutável": 0}
    houses_counts = {house: {"casa": house, "contagem": 0, "planetas": []} for house in range(1, 13)}
    avisos: List[str] = []

    cusps = chart.get("houses", {}).get("cusps") or []
    planets = chart.get("planets", {})

    for name in PLANETS.keys():
        planet = planets.get(name)
        if not planet:
            avisos.append(f"Planeta ausente: {name}.")
            continue
        sign = planet.get("sign")
        lon = planet.get("lon")
        if sign is None or lon is None:
            avisos.append(f"Sem signo/longitude para {name}.")
            continue
        element = ELEMENT_MAP.get(sign)
        modality = MODALITY_MAP.get(sign)
        if element:
            elements[element] += 1
        else:
            avisos.append(f"Elemento não mapeado para {name}.")
        if modality:
            modalities[modality] += 1
        else:
            avisos.append(f"Modalidade não mapeada para {name}.")

        house = _house_for_lon(cusps, float(lon))
        houses_counts[house]["contagem"] += 1
        houses_counts[house]["planetas"].append(planet_key_to_ptbr(name))

    dominant_element = max(elements.items(), key=lambda item: item[1])[0]
    dominant_modality = max(modalities.items(), key=lambda item: item[1])[0]
    houses_sorted = sorted(houses_counts.values(), key=lambda item: item["contagem"], reverse=True)
    top_houses = [item["casa"] for item in houses_sorted[:3]]

    payload = {
        "elementos": elements,
        "modalidades": modalities,
        "casas": list(houses_counts.values()),
        "dominancias": {
            "elemento_dominante": dominant_element,
            "modalidade_dominante": dominant_modality,
            "casas_mais_ativadas": top_houses,
        },
        "metadados": {"fonte": "natal", "version": "v1"},
    }
    payload["metadados"].update(
        metadata
        if metadata is not None
        else _build_time_metadata(timezone=None, tz_offset_minutes=None, local_dt=None)
    )
    if avisos:
        payload["avisos"] = avisos
    return payload

def _solar_return_datetime(
    natal_dt: datetime,
    target_year: int,
    tz_offset_minutes: int,
    request: Request,
    user_id: Optional[str] = None,
) -> datetime:
    v1_dt = solar_return_datetime(
        natal_dt=natal_dt,
        target_year=target_year,
        tz_offset_minutes=tz_offset_minutes,
        engine="v1",
    )

    if SOLAR_RETURN_ENGINE == "v2":
        try:
            v2_dt = solar_return_datetime(
                natal_dt=natal_dt,
                target_year=target_year,
                tz_offset_minutes=tz_offset_minutes,
                engine="v2",
            )
            diff_seconds = abs((v2_dt - v1_dt).total_seconds())
            _log(
                "info",
                "solar_return_engine_compare",
                request_id=getattr(request.state, "request_id", None),
                path=request.url.path,
                status=200,
                latency_ms=None,
                user_id=user_id,
                v1_utc=v1_dt.isoformat(),
                v2_utc=v2_dt.isoformat(),
                diff_seconds=round(diff_seconds, 3),
            )
        except Exception:
            logger.error(
                "solar_return_engine_compare_error",
                exc_info=True,
                extra={
                    "request_id": getattr(request.state, "request_id", None),
                    "path": request.url.path,
                    "user_id": user_id,
                },
            )

    return v1_dt


PROFILE_DEFAULT_ASPECTS = ["conj", "opos", "quad", "tri", "sext"]
PROFILE_DEFAULT_ORB_MAX = 5.0

PLANET_WEIGHTS = {
    "Moon": 1.0,
    "Mercury": 1.5,
    "Venus": 1.5,
    "Sun": 1.5,
    "Mars": 2.2,
    "Jupiter": 2.5,
    "Saturn": 3.3,
    "Uranus": 3.0,
    "Neptune": 3.0,
    "Pluto": 3.6,
}

ASPECT_WEIGHTS = {
    "conjunction": 1.0,
    "opposition": 0.95,
    "square": 0.95,
    "trine": 0.70,
    "sextile": 0.55,
}

TARGET_WEIGHTS = {
    "Sun": 1.25,
    "Moon": 1.25,
    "ASC": 1.25,
    "MC": 1.25,
}

DURATION_FACTORS = {
    "Moon": 0.85,
    "Mercury": 0.85,
    "Venus": 0.85,
    "Sun": 0.85,
    "Mars": 0.90,
    "Jupiter": 1.00,
    "Saturn": 1.00,
    "Uranus": 1.00,
    "Neptune": 1.00,
    "Pluto": 1.00,
}

PLANET_TAGS = {
    "Sun": ["Identidade", "Direção"],
    "Moon": ["Emoções", "Necessidades"],
    "Mercury": ["Comunicação", "Decisão"],
    "Venus": ["Relacionamentos", "Valor"],
    "Mars": ["Ação", "Coragem"],
    "Jupiter": ["Expansão", "Oportunidade"],
    "Saturn": ["Estrutura", "Responsabilidade"],
    "Uranus": ["Mudança", "Ruptura"],
    "Neptune": ["Inspiração", "Sensibilidade"],
    "Pluto": ["Transformação", "Intensidade"],
}

ASPECT_TAGS = {
    "conjunction": ["Intensidade"],
    "opposition": ["Tensão"],
    "square": ["Ajuste"],
    "trine": ["Fluxo"],
    "sextile": ["Abertura"],
}


def _resolve_preferencias_profile(preferencias: Optional[PreferenciasPerfil]) -> str:
    if preferencias is None:
        return "padrao"
    if preferencias.perfil is None:
        return "custom"
    return preferencias.perfil


def _resolve_orb_max(
    orbes: Optional[Dict[str, float]], preferencias: Optional[PreferenciasPerfil]
) -> float:
    if preferencias and preferencias.orb_max_deg is not None:
        return float(preferencias.orb_max_deg)
    if orbes:
        return max(float(value) for value in orbes.values())
    return PROFILE_DEFAULT_ORB_MAX


def _apply_profile_defaults(
    aspectos_habilitados: Optional[List[str]],
    orbes: Optional[Dict[str, float]],
    preferencias: Optional[PreferenciasPerfil],
) -> tuple[Optional[List[str]], Optional[Dict[str, float]], float, str]:
    profile = _resolve_preferencias_profile(preferencias)
    orb_max = _resolve_orb_max(orbes, preferencias)
    if profile == "padrao":
        if aspectos_habilitados is None:
            aspectos_habilitados = list(PROFILE_DEFAULT_ASPECTS)
        if orbes is None:
            orbes = {aspecto: PROFILE_DEFAULT_ORB_MAX for aspecto in aspectos_habilitados}
        orb_max = PROFILE_DEFAULT_ORB_MAX
    return aspectos_habilitados, orbes, orb_max, profile


def _apply_solar_return_profile(
    preferencias: Optional[SolarReturnPreferencias],
) -> tuple[Optional[List[str]], Optional[Dict[str, float]], float, str]:
    if preferencias is None:
        perfil = "padrao"
    elif preferencias.perfil is None:
        perfil = "custom"
    else:
        perfil = preferencias.perfil
    aspectos_habilitados = preferencias.aspectos_habilitados if preferencias else None
    orbes = preferencias.orbes if preferencias else None
    orb_max = (
        float(preferencias.orb_max_deg)
        if preferencias and preferencias.orb_max_deg is not None
        else _resolve_orb_max(orbes, None)
    )
    if perfil == "padrao":
        if aspectos_habilitados is None:
            aspectos_habilitados = list(PROFILE_DEFAULT_ASPECTS)
        if orbes is None:
            orbes = {aspecto: PROFILE_DEFAULT_ORB_MAX for aspecto in aspectos_habilitados}
        orb_max = PROFILE_DEFAULT_ORB_MAX
    return aspectos_habilitados, orbes, orb_max, perfil


def _house_for_lon(cusps: List[float], lon: float) -> int:
    if not cusps:
        return 1
    lon_mod = lon % 360
    for idx in range(12):
        start = float(cusps[idx])
        end = float(cusps[(idx + 1) % 12])
        start_mod = start
        end_mod = end
        lon_check = lon_mod
        if end_mod < start_mod:
            end_mod += 360
            if lon_check < start_mod:
                lon_check += 360
        if start_mod <= lon_check < end_mod:
            return idx + 1
    return 12


def _impact_score(
    transit_planet: str,
    aspect: str,
    target: str,
    orb_deg: float,
    orb_max: float,
) -> float:
    if orb_max <= 0:
        orb_max = PROFILE_DEFAULT_ORB_MAX
    planet_weight = PLANET_WEIGHTS.get(transit_planet, 1.0)
    aspect_weight = ASPECT_WEIGHTS.get(aspect, 0.5)
    target_weight = TARGET_WEIGHTS.get(target, 1.0)
    duration_factor = DURATION_FACTORS.get(transit_planet, 1.0)
    orb_factor = max(0.0, min(1.0, 1.0 - (orb_deg / orb_max)))
    score = 100 * planet_weight * aspect_weight * target_weight * orb_factor * duration_factor
    return round(min(score, 100.0), 2)


def _severity_for(score: float) -> str:
    if score >= 70:
        return "ALTA"
    if score >= 45:
        return "MEDIA"
    return "BAIXA"


def _event_tags(transit_planet: str, aspect: str) -> List[str]:
    tags = []
    tags.extend(PLANET_TAGS.get(transit_planet, []))
    tags.extend(ASPECT_TAGS.get(aspect, []))
    seen = set()
    result = []
    for tag in tags:
        if tag not in seen:
            result.append(tag)
            seen.add(tag)
    return result[:4]


def _build_event_copy(transitando: str, aspecto: str, alvo: str, tags: List[str]) -> TransitEventCopy:
    tag_base = tags[0] if tags else "foco"
    return TransitEventCopy(
        headline=f"{transitando} em {aspecto} com {alvo}",
        mecanica=f"Trânsito enfatiza {tag_base.lower()} em temas ligados a {alvo}.",
        use_bem="Tendência a favorecer clareza e ação prática quando você organiza prioridades.",
        risco="Pede atenção a impulsos e excesso de carga; ajuste o ritmo com consistência.",
    )


def _build_transit_event(
    aspect: Dict[str, Any],
    date_str: str,
    natal_chart: Dict[str, Any],
    orb_max: float,
) -> TransitEvent:
    transit_planet = aspect["transit_planet"]
    natal_planet = aspect["natal_planet"]
    aspect_key = aspect["aspect"]
    orb_deg = float(aspect.get("orb", 0.0))
    transitando_pt = planet_key_to_ptbr(transit_planet)
    alvo_pt = planet_key_to_ptbr(natal_planet)
    aspect_pt = aspect_to_ptbr(aspect_key)
    tags = _event_tags(transit_planet, aspect_key)
    score = _impact_score(transit_planet, aspect_key, natal_planet, orb_deg, orb_max)
    event_hash = hashlib.sha1(
        f"{date_str}:{transit_planet}:{natal_planet}:{aspect_key}:{round(orb_deg,2)}".encode("utf-8")
    ).hexdigest()
    date_start = f"{date_str}T00:00:00Z"
    date_peak = f"{date_str}T12:00:00Z"
    date_end = f"{date_str}T23:59:59Z"
    natal_cusps = natal_chart.get("houses", {}).get("cusps", [])
    natal_lon = float(natal_chart.get("planets", {}).get(natal_planet, {}).get("lon", 0.0))
    return TransitEvent(
        event_id=event_hash,
        date_range=TransitEventDateRange(start_utc=date_start, peak_utc=date_peak, end_utc=date_end),
        transitando=transitando_pt,
        alvo_tipo="PLANETA_NATAL",
        alvo=alvo_pt,
        aspecto=aspect_pt,
        orb_graus=round(orb_deg, 2),
        casa_ativada=_house_for_lon(natal_cusps, natal_lon) if natal_cusps else None,
        tags=tags,
        severidade=_severity_for(score),
        impact_score=score,
        copy=_build_event_copy(transitando_pt, aspect_pt, alvo_pt, tags),
    )


def _daily_summary(phase: str, sign: str) -> Dict[str, str]:
    sign_pt = sign_to_ptbr(sign)
    templates = {
        "new_moon": {
            "tom": "Início de ciclo com foco em intenção e organização.",
            "gatilho": f"Tendência a priorizar decisões ligadas a {sign_pt}.",
            "acao": "Defina uma ação simples e mantenha o ritmo ao longo do dia.",
        },
        "waxing": {
            "tom": "Fase de avanço com energia de construção.",
            "gatilho": f"Tendência a buscar progresso em temas de {sign_pt}.",
            "acao": "Escolha uma meta prática e execute em etapas curtas.",
        },
        "full_moon": {
            "tom": "Pico de visibilidade e ajustes de equilíbrio.",
            "gatilho": f"Tendência a perceber resultados em assuntos de {sign_pt}.",
            "acao": "Revisite o que já foi iniciado e faça correções objetivas.",
        },
        "waning": {
            "tom": "Fase de depuração e reorganização.",
            "gatilho": f"Tendência a limpar excessos em temas de {sign_pt}.",
            "acao": "Finalize pendências e reduza ruídos antes de seguir.",
        },
    }
    return templates.get(phase, templates["waxing"])


def _summary_from_event(event: TransitEvent) -> Dict[str, str]:
    tags = event.tags or []
    tag = tags[0] if tags else "foco"
    return {
        "tom": f"Tendência a concentrar energia em {tag.lower()}.",
        "gatilho": f"{event.transitando} em {event.aspecto} com {event.alvo} pede atenção a prioridades.",
        "acao": "Aja com consistência e ajuste o ritmo conforme o contexto.",
    }


def _curate_daily_events(events: List[TransitEvent]) -> Dict[str, Any]:
    if not events:
        return {
            "top_event": None,
            "trigger_event": None,
            "secondary_events": [],
            "summary": None,
        }
    ordered = sorted(events, key=lambda item: item.impact_score, reverse=True)
    top_event = ordered[0]
    trigger_event = next(
        (item for item in ordered if item.transitando == "Marte" and item.impact_score >= 55),
        None,
    )
    if trigger_event is None and len(ordered) > 1:
        trigger_event = ordered[1]
    secondary_pool = [item for item in ordered[1:] if item != trigger_event]
    secondary_events = secondary_pool[:2]
    summary = _summary_from_event(top_event)
    return {
        "top_event": top_event,
        "trigger_event": trigger_event,
        "secondary_events": secondary_events,
        "summary": summary,
    }

def _strength_from_score(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "low"

def _icon_for_tags(tags: List[str]) -> str:
    tag_map = {
        "trabalho": "💼",
        "carreira": "💼",
        "relacionamentos": "💞",
        "amor": "💞",
        "emoções": "🌙",
        "emocional": "🌙",
        "energia": "🔥",
        "corpo": "🔥",
        "foco": "🎯",
    }
    for tag in tags:
        key = tag.lower()
        if key in tag_map:
            return tag_map[key]
    return "✨"

def _build_transits_context(
    body: TransitsRequest,
    tz_offset_minutes: int,
    lang: Optional[str],
    date_override: Optional[str] = None,
    preferencias: Optional[PreferenciasPerfil] = None,
) -> Dict[str, Any]:
    target_date = date_override or body.target_date
    if not target_date:
        raise HTTPException(status_code=422, detail="Informe target_date ou range.")
    target_y, target_m, target_d = _parse_date_yyyy_mm_dd(target_date)
    aspectos_habilitados, orbes, orb_max, profile = _apply_profile_defaults(
        body.aspectos_habilitados,
        body.orbes,
        preferencias if preferencias is not None else body.preferencias,
    )

    natal_chart = compute_chart(
        year=body.natal_year,
        month=body.natal_month,
        day=body.natal_day,
        hour=body.natal_hour,
        minute=body.natal_minute,
        second=body.natal_second,
        lat=body.lat,
        lng=body.lng,
        tz_offset_minutes=tz_offset_minutes,
        house_system=body.house_system.value,
        zodiac_type=body.zodiac_type.value,
        ayanamsa=body.ayanamsa,
    )

    transit_chart = compute_transits(
        target_year=target_y,
        target_month=target_m,
        target_day=target_d,
        lat=body.lat,
        lng=body.lng,
        tz_offset_minutes=tz_offset_minutes,
        zodiac_type=body.zodiac_type.value,
        ayanamsa=body.ayanamsa,
    )

    natal_chart = _apply_sign_localization(natal_chart, lang)
    transit_chart = _apply_sign_localization(transit_chart, lang)

    aspects_config, aspectos_usados, orbes_usados = resolve_aspects_config(
        aspectos_habilitados,
        orbes,
    )
    aspects = compute_transit_aspects(
        transit_planets=transit_chart["planets"],
        natal_planets=natal_chart["planets"],
        aspects=aspects_config,
    )

    return {
        "natal": natal_chart,
        "transits": transit_chart,
        "aspects": aspects,
        "aspectos_usados": aspectos_usados,
        "orbes_usados": orbes_usados,
        "orb_max": orb_max,
        "profile": profile,
    }


def _build_transit_events_for_date(date_str: str, context: Dict[str, Any]) -> List[TransitEvent]:
    events: List[TransitEvent] = []
    natal_chart = context["natal"]
    for aspect in context["aspects"]:
        events.append(_build_transit_event(aspect, date_str, natal_chart, context["orb_max"]))
    events.sort(key=lambda item: item.impact_score, reverse=True)
    return events

def _areas_activated(aspects: List[Dict[str, Any]], moon_phase: Optional[str] = None) -> List[Dict[str, Any]]:
    base_score = 50.0
    orb_max_default = 6.0

    area_config = {
        "Emoções": {"planets": {"Moon", "Neptune", "Pluto"}},
        "Relações": {"planets": {"Venus", "Mars"}},
        "Trabalho": {"planets": {"Sun", "Saturn", "Jupiter"}},
        "Corpo": {"planets": {"Mars", "Saturn", "Sun"}},
    }

    scores: Dict[str, Dict[str, Any]] = {
        area: {"score": base_score, "top_aspect": None, "top_weight": 0.0}
        for area in area_config.keys()
    }

    aspect_weights = {
        "conjunction": 14,
        "opposition": 14,
        "square": 12,
        "trine": 9,
        "sextile": 7,
    }
    supportive = {"trine", "sextile"}
    challenging = {"square", "opposition"}
    conjunction_positive = {"Venus", "Jupiter"}
    conjunction_negative = {"Mars", "Saturn", "Pluto"}

    for asp in aspects:
        aspect_type = asp.get("aspect")
        if aspect_type not in aspect_weights:
            continue
        orb = float(asp.get("orb", 0.0))
        orb_max = orb_max_default
        weight = aspect_weights[aspect_type] * max(0.0, 1.0 - (orb / orb_max))

        sign = 0.0
        if aspect_type in supportive:
            sign = 1.0
        elif aspect_type in challenging:
            sign = -1.0
        elif aspect_type == "conjunction":
            planets = {asp.get("transit_planet"), asp.get("natal_planet")}
            if planets & conjunction_negative:
                sign = -0.5
            elif planets & conjunction_positive:
                sign = 0.5

        for area, config in area_config.items():
            if asp.get("transit_planet") in config["planets"] or asp.get("natal_planet") in config["planets"]:
                scores[area]["score"] += weight * sign
                if abs(weight * sign) > scores[area]["top_weight"]:
                    scores[area]["top_weight"] = abs(weight * sign)
                    scores[area]["top_aspect"] = asp

    if moon_phase in {"full_moon", "new_moon"}:
        scores["Emoções"]["score"] += 3

    items = []
    for area, data in scores.items():
        score = max(0, min(100, round(data["score"], 1)))
        if score <= 34:
            level = "low"
        elif score <= 59:
            level = "medium"
        elif score <= 79:
            level = "high"
        else:
            level = "intense"

        reason = "No strong aspects detected."
        if data["top_aspect"]:
            asp = data["top_aspect"]
            reason = (
                f"Top aspect: {asp.get('transit_planet')} {asp.get('aspect')} {asp.get('natal_planet')}."
            )

        items.append(
            {
                "area": area,
                "level": level,
                "score": score,
                "reason": reason,
            }
        )

    return items

def _now_yyyy_mm_dd() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _git_commit_hash() -> Optional[str]:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent)
            .decode()
            .strip()
        )
    except Exception:
        return None


def _mercury_alert_for(date: str, lat: float, lng: float, tz_offset_minutes: int) -> Optional[SystemAlert]:
    """Return a Mercury retrograde alert for a validated YYYY-MM-DD date.

    The date is parsed through ``_parse_date_yyyy_mm_dd`` to guarantee a clear
    400 error for bad inputs (instead of silent ValueErrors) and to avoid
    duplicating manual ``split("-")`` logic. Keeping a single, validated parse
    path is the correct resolution for merge conflicts that show a second
    ``compute_transits`` call using ``date.split("-")``: we only need one
    transit computation after validation.
    """

    y, m, d = _parse_date_yyyy_mm_dd(date)
    chart = compute_transits(
        target_year=y,
        target_month=m,
        target_day=d,
        lat=lat,
        lng=lng,
        tz_offset_minutes=tz_offset_minutes,
    )
    mercury = chart.get("planets", {}).get("Mercury")
    if not mercury or mercury.get("speed") is None:
        return None

    retro = mercury.get("retrograde")
    if retro:
        return SystemAlert(
            id="mercury_retrograde",
            severity="medium",
            title="Mercúrio retrógrado",
            body="Mercúrio está em retrogradação. Revise comunicações e contratos com atenção.",
            technical={"mercury_speed": mercury.get("speed"), "mercury_lon": mercury.get("lon")},
        )
    return None


def _daily_notifications_payload(date: str, lat: float, lng: float, tz_offset_minutes: int) -> NotificationsDailyResponse:
    moon = compute_moon_only(date, tz_offset_minutes=tz_offset_minutes)
    phase = _moon_phase_4(moon["phase_angle_deg"])
    sign = moon["moon_sign"]

    items: List[Dict[str, Any]] = [
        {
            "type": "cosmic_weather",
            "title": f"Lua {phase} em {sign}",
            "body": _cw_text(phase, sign),
        }
    ]

    mercury_alert = _mercury_alert_for(date, lat, lng, tz_offset_minutes)
    if mercury_alert:
        items.append(
            {
                "type": "system_alert",
                "title": mercury_alert.title,
                "body": mercury_alert.body,
                "technical": mercury_alert.technical,
            }
        )

    return NotificationsDailyResponse(date=date, items=items, items_ptbr=items)


def _tz_offset_for(
    date_time: datetime,
    timezone: Optional[str],
    fallback_minutes: Optional[int],
    strict: bool = False,
    request_id: Optional[str] = None,
    path: Optional[str] = None,
    prefer_fold: Optional[int] = None,
) -> int:
    """Resolve timezone: prefer IANA name; fallback to explicit offset or UTC.

    When ``strict`` is True, detect ambiguous DST transitions and reject them with a
    helpful error so birth datetimes não fiquem "um dia antes" por causa de fuso mal
    resolvido.
    """
    warnings: List[str] = []

    if timezone:
        try:
            tzinfo = ZoneInfo(timezone)
        except ZoneInfoNotFoundError:
            _log(
                "warning",
                "timezone_invalid",
                request_id=request_id,
                path=path,
                timezone=timezone,
                local_datetime=date_time.isoformat(),
                warnings=["invalid_timezone"],
            )
            raise HTTPException(status_code=400, detail=f"Timezone inválido: {timezone}")

        offset_fold0 = date_time.replace(tzinfo=tzinfo, fold=0).utcoffset()
        offset_fold1 = date_time.replace(tzinfo=tzinfo, fold=1).utcoffset()

        # Escolhe o offset padrão (compatível com o comportamento anterior)
        offset = offset_fold0 or offset_fold1
        if offset is None:
            _log(
                "warning",
                "timezone_offset_missing",
                request_id=request_id,
                path=path,
                timezone=timezone,
                local_datetime=date_time.isoformat(),
                warnings=["missing_offset"],
            )
            raise HTTPException(status_code=400, detail=f"Timezone sem offset disponível: {timezone}")

        if strict and offset_fold0 and offset_fold1 and offset_fold0 != offset_fold1:
            # horário ambíguo na virada de DST
            opts = sorted({int(offset_fold0.total_seconds() // 60), int(offset_fold1.total_seconds() // 60)})
            _log(
                "warning",
                "timezone_ambiguous",
                request_id=request_id,
                path=path,
                timezone=timezone,
                offset_options_minutes=opts,
                offset_fold0_minutes=int(offset_fold0.total_seconds() // 60),
                offset_fold1_minutes=int(offset_fold1.total_seconds() // 60),
                fold=None,
                local_datetime=date_time.isoformat(),
                warnings=["ambiguous_time"],
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "detail": "Horário ambíguo na transição de horário de verão.",
                    "offset_options_minutes": opts,
                    "hint": "Envie tz_offset_minutes explicitamente ou ajuste o horário local.",
                },
            )

        if offset_fold0 and offset_fold1 and offset_fold0 != offset_fold1:
            warnings.append("ambiguous_time")

        resolved_offset = int(offset.total_seconds() // 60)
        fold = 0 if offset_fold0 is not None else 1
        utc_dt = date_time - timedelta(minutes=resolved_offset)
        _log(
            "info",
            "timezone_resolved",
            request_id=request_id,
            path=path,
            timezone=timezone,
            offset_minutes=resolved_offset,
            offset_fold0_minutes=int(offset_fold0.total_seconds() // 60) if offset_fold0 else None,
            offset_fold1_minutes=int(offset_fold1.total_seconds() // 60) if offset_fold1 else None,
            fold=fold,
            local_datetime=date_time.isoformat(),
            utc_datetime=utc_dt.isoformat(),
            warnings=warnings,
        )
        return resolved_offset

    if fallback_minutes is not None:
        warnings.append("fallback_offset_used")
        utc_dt = date_time - timedelta(minutes=fallback_minutes)
        _log(
            "info",
            "timezone_resolved",
            request_id=request_id,
            path=path,
            timezone=None,
            offset_minutes=fallback_minutes,
            offset_fold0_minutes=None,
            offset_fold1_minutes=None,
            fold=None,
            local_datetime=date_time.isoformat(),
            utc_datetime=utc_dt.isoformat(),
            warnings=warnings,
        )
        return fallback_minutes

    warnings.append("timezone_missing_default_utc")
    _log(
        "info",
        "timezone_resolved",
        request_id=request_id,
        path=path,
        timezone=None,
        offset_minutes=0,
        offset_fold0_minutes=None,
        offset_fold1_minutes=None,
        fold=None,
        local_datetime=date_time.isoformat(),
        utc_datetime=date_time.isoformat(),
        warnings=warnings,
    )
    return 0
    try:
        resolved = resolve_timezone_offset(
            date_time=date_time,
            timezone=timezone,
            fallback_minutes=fallback_minutes,
            strict=strict,
            prefer_fold=prefer_fold,
        )
    except TimezoneResolutionError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc

    return resolved.offset_minutes


def _resolve_fold_for(
    date_time: Optional[datetime],
    timezone: Optional[str],
    tz_offset_minutes: Optional[int],
) -> Optional[int]:
    if date_time is None or not timezone or tz_offset_minutes is None:
        return None

    try:
        tzinfo = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return None

    target_offset = timedelta(minutes=tz_offset_minutes)
    offset_fold0 = date_time.replace(tzinfo=tzinfo, fold=0).utcoffset()
    offset_fold1 = date_time.replace(tzinfo=tzinfo, fold=1).utcoffset()

    if offset_fold0 == target_offset:
        return 0
    if offset_fold1 == target_offset:
        return 1
    return None


def _build_time_metadata(
    *,
    timezone: Optional[str],
    tz_offset_minutes: Optional[int],
    local_dt: Optional[datetime],
    avisos: Optional[List[str]] = None,
) -> Dict[str, Any]:
    utc_dt = (
        local_dt - timedelta(minutes=tz_offset_minutes)
        if local_dt is not None and tz_offset_minutes is not None
        else None
    )
    return {
        "timezone_resolvida": timezone,
        "timezone_usada": timezone,
        "tz_offset_minutes_usado": tz_offset_minutes,
        "tz_offset_minutes": tz_offset_minutes,
        "fold_usado": _resolve_fold_for(local_dt, timezone, tz_offset_minutes),
        "datetime_local_usado": local_dt.isoformat() if local_dt else None,
        "datetime_utc_usado": utc_dt.isoformat() if utc_dt else None,
        "avisos": avisos or [],
    }

def _json_error_response(
    request: Request,
    status_code: int,
    error: str,
    message: str,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    payload = {
        "error": error,
        "message": message,
        "request_id": request_id,
    }
    return JSONResponse(status_code=status_code, content=payload, headers={"X-Request-Id": request_id})


# -----------------------------
# Cache TTLs
# -----------------------------
TTL_NATAL_SECONDS = 30 * 24 * 3600
TTL_TRANSITS_SECONDS = 6 * 3600
TTL_RENDER_SECONDS = 30 * 24 * 3600
TTL_COSMIC_WEATHER_SECONDS = 6 * 3600


def _cosmic_weather_payload(
    date_str: str,
    timezone: Optional[str],
    tz_offset_minutes: Optional[int],
    user_id: str,
    lang: Optional[str] = None,
    request_id: Optional[str] = None,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute (or fetch) the cosmic weather payload for a single day."""

    _parse_date_yyyy_mm_dd(date_str)
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=12, minute=0, second=0)
    resolved_offset = _tz_offset_for(
        dt,
        timezone,
        tz_offset_minutes,
        request_id=request_id,
        path=path,
    )

    lang_key = (lang or "").lower()
    cache_key = f"cw:{user_id}:{date_str}:{timezone}:{resolved_offset}:{lang_key}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    moon = compute_moon_only(date_str, tz_offset_minutes=resolved_offset)
    phase = _moon_phase_4(moon["phase_angle_deg"])
    sign = moon["moon_sign"]
    phase_label = _moon_phase_label_pt(phase)

    payload = {
        "date": date_str,
        "moon_phase": phase,
        "moon_sign": sign,
        "deg_in_sign": moon.get("deg_in_sign"),
        "headline": f"Lua {phase_label} em {sign}",
        "text": _cw_text(phase, sign),
        "top_event": None,
        "trigger_event": None,
        "secondary_events": [],
        "summary": _daily_summary(phase, sign),
    }

    payload = _apply_moon_localization(payload, lang)
    payload.update(_build_cosmic_weather_ptbr(payload))
    payload["headline_ptbr"] = payload.get("headline")
    payload["resumo_ptbr"] = payload.get("text")
    payload["metadados_tecnicos"] = {
        "idioma": "pt-BR",
        "fonte_traducao": "backend",
    }
    payload["metadados_tecnicos"].update(
        _build_time_metadata(
            timezone=timezone,
            tz_offset_minutes=resolved_offset,
            local_dt=dt,
        )
    )

    cache.set(cache_key, payload, ttl_seconds=TTL_COSMIC_WEATHER_SECONDS)
    return payload

ROADMAP_FEATURES = {
    "notifications": {"status": "beta", "notes": "feed diário via API; push aguardando provedor"},
    "mercury_retrograde_alert": {
        "status": "beta",
        "notes": "alertas sistêmicos quando Mercúrio entrar/saír de retrogradação",
    },
    "life_cycles": {"status": "planned", "notes": "mapear ciclos de retorno e progressões"},
    "auto_timezone": {"status": "beta", "notes": "usa timezone IANA no payload ou resolver via endpoint"},
    "tests": {"status": "in_progress", "notes": "priorizar casos críticos de cálculo"},
}

ENDPOINTS_CATALOG = [
    {
        "method": "GET",
        "path": "/",
        "auth_required": False,
        "headers_required": [],
        "request_model": None,
        "response_model": None,
        "description": "Status básico do serviço.",
    },
    {
        "method": "GET",
        "path": "/health",
        "auth_required": False,
        "headers_required": [],
        "request_model": None,
        "response_model": None,
        "description": "Health check simples.",
    },
    {
        "method": "GET",
        "path": "/v1/system/roadmap",
        "auth_required": False,
        "headers_required": [],
        "request_model": None,
        "response_model": None,
        "description": "Roadmap do produto.",
    },
    {
        "method": "GET",
        "path": "/v1/system/endpoints",
        "auth_required": False,
        "headers_required": [],
        "request_model": None,
        "response_model": None,
        "description": "Lista de endpoints (dev-only).",
    },
    {
        "method": "GET",
        "path": "/v1/account/status",
        "path": "/v1/account/plan",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": None,
        "response_model": None,
        "description": "Status da conta e do plano.",
    },
    {
        "method": "POST",
        "path": "/v1/account/plan-status",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": None,
        "response_model": None,
        "description": "Status do plano para tela Plano.",
    },
    {
        "method": "POST",
        "path": "/v1/synastry/compare",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "SynastryRequest",
        "response_model": None,
        "description": "Comparação básica de sinastria.",
        "description": "Plano da conta e informações de trial.",
    },
    {
        "method": "POST",
        "path": "/v1/time/resolve-tz",
        "auth_required": False,
        "headers_required": [],
        "request_model": "TimezoneResolveRequest",
        "response_model": None,
        "description": "Resolve offset de timezone.",
    },
    {
        "method": "GET",
        "path": "/v1/daily/summary",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": None,
        "response_model": None,
        "description": "Resumo diário consolidado.",
    },
    {
        "method": "POST",
        "path": "/v1/time/validate-local-datetime",
        "auth_required": False,
        "headers_required": [],
        "request_model": "ValidateLocalDatetimeRequest",
        "response_model": None,
        "description": "Valida data/hora local e resolve UTC com tratamento de DST.",
    },
    {
        "method": "POST",
        "path": "/v1/diagnostics/ephemeris-check",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "EphemerisCheckRequest",
        "response_model": None,
        "description": "Diagnóstico do Swiss Ephemeris.",
    },
    {
        "method": "POST",
        "path": "/v1/insights/mercury-retrograde",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "MercuryRetrogradeRequest",
        "response_model": None,
        "description": "Insight sobre retrogradação de Mercúrio.",
    },
    {
        "method": "POST",
        "path": "/v1/insights/dominant-theme",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "TransitsRequest",
        "response_model": None,
        "description": "Tema dominante do período.",
    },
    {
        "method": "POST",
        "path": "/v1/insights/areas-activated",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "TransitsRequest",
        "response_model": None,
        "description": "Áreas ativadas do mapa.",
    },
    {
        "method": "POST",
        "path": "/v1/insights/care-suggestion",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "TransitsRequest",
        "response_model": None,
        "description": "Sugestões de cuidado.",
    },
    {
        "method": "POST",
        "path": "/v1/insights/life-cycles",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "TransitsRequest",
        "response_model": None,
        "description": "Ciclos de vida.",
    },
    {
        "method": "POST",
        "path": "/v1/insights/solar-return",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "TransitsRequest",
        "response_model": "SolarReturnResponse",
        "description": "Retorno solar (insight).",
    },
    {
        "method": "POST",
        "path": "/v1/chart/natal",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "NatalChartRequest",
        "response_model": None,
        "description": "Mapa natal completo.",
    },
    {
        "method": "POST",
        "path": "/v1/chart/transits",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "TransitsRequest",
        "response_model": None,
        "description": "Mapa de trânsitos.",
    },
    {
        "method": "POST",
        "path": "/v1/transits/events",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "TransitsEventsRequest",
        "response_model": "TransitEventsResponse",
        "description": "Eventos de trânsito curados (determinístico).",
    },
    {
        "method": "GET",
        "path": "/v1/transits/next-days",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": None,
        "response_model": None,
        "description": "Lista dos próximos dias com resumo de trânsitos.",
    },
    {
        "method": "GET",
        "path": "/v1/transits/personal-today",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": None,
        "response_model": None,
        "description": "Trânsitos pessoais do dia.",
    },
    {
        "method": "GET",
        "path": "/v1/cosmic-timeline/next-7-days",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": None,
        "response_model": None,
        "description": "Timeline cósmica de 7 dias.",
    },
    {
        "method": "GET",
        "path": "/v1/revolution-solar/current-year",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": None,
        "response_model": None,
        "description": "Resumo do ano atual (RS + progressão + lunação).",
    },
    {
        "method": "GET",
        "path": "/v1/moon/timeline",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": None,
        "response_model": "CosmicWeatherRangeResponse",
        "description": "Timeline lunar (intervalo de datas).",
    },
    {
        "method": "POST",
        "path": "/v1/chart/render-data",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "RenderDataRequest",
        "response_model": None,
        "description": "Dados simplificados para renderização.",
    },
    {
        "method": "POST",
        "path": "/v1/chart/distributions",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "NatalChartRequest",
        "response_model": None,
        "description": "Distribuições de elementos/modalidades/casas.",
    },
    {
        "method": "POST",
        "path": "/v1/interpretation/natal",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "NatalChartRequest",
        "response_model": None,
        "description": "Resumo geral do mapa natal.",
    },
    {
        "method": "GET",
        "path": "/v1/cosmic-weather",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": None,
        "response_model": "CosmicWeatherResponse",
        "description": "Clima cósmico do dia.",
    },
    {
        "method": "GET",
        "path": "/v1/cosmic-weather/range",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": None,
        "response_model": "CosmicWeatherRangeResponse",
        "description": "Clima cósmico em intervalo.",
    },
    {
        "method": "GET",
        "path": "/v1/alerts/system",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": None,
        "response_model": "SystemAlertsResponse",
        "description": "Alertas sistêmicos.",
    },
    {
        "method": "GET",
        "path": "/v1/alerts/retrogrades",
        "auth_required": False,
        "headers_required": [],
        "request_model": None,
        "response_model": None,
        "description": "Alertas de retrogradação.",
    },
    {
        "method": "GET",
        "path": "/v1/notifications/daily",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": None,
        "response_model": "NotificationsDailyResponse",
        "description": "Notificações diárias.",
    },
    {
        "method": "POST",
        "path": "/v1/solar-return/calculate",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "SolarReturnRequest",
        "response_model": None,
        "description": "Cálculo completo de revolução solar.",
    },
    {
        "method": "POST",
        "path": "/v1/solar-return/overlay",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "SolarReturnOverlayRequest",
        "response_model": None,
        "description": "Sobreposição RS × Natal.",
    },
    {
        "method": "POST",
        "path": "/v1/solar-return/timeline",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "SolarReturnTimelineRequest",
        "response_model": None,
        "description": "Timeline anual (Sol em aspectos).",
    },
    {
        "method": "POST",
        "path": "/v1/ai/cosmic-chat",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "CosmicChatRequest",
        "response_model": None,
        "description": "Chat interpretativo com IA.",
    },
    {
        "method": "POST",
        "path": "/v1/lunations/calculate",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "LunationCalculateRequest",
        "response_model": "LunationCalculateResponse",
        "description": "Cálculo de lunação.",
    },
    {
        "method": "POST",
        "path": "/v1/progressions/secondary/calculate",
        "auth_required": True,
        "headers_required": ["Authorization", "X-User-Id"],
        "request_model": "SecondaryProgressionCalculateRequest",
        "response_model": "SecondaryProgressionCalculateResponse",
        "description": "Progressões secundárias.",
    },
]

# -----------------------------
# Routes
# -----------------------------
@app.get("/")
async def root():
    """Lightweight root endpoint for uptime checks and Render probes."""
    return {
        "ok": True,
        "service": "astroengine",
        "version": app.version,
        "commit": _git_commit_hash(),
        "env": {"openai": bool(os.getenv("OPENAI_API_KEY")), "log_level": LOG_LEVEL},
    }


@app.get("/health")
async def health_check():
    return {"ok": True}


@app.get("/v1/system/roadmap")
async def roadmap():
    """Visão rápida do andamento das próximas funcionalidades."""
    return {
        "features": ROADMAP_FEATURES,
        "metadados_tecnicos": {
            "idioma": "pt-BR",
            "fonte_traducao": "backend",
            **_build_time_metadata(timezone=None, tz_offset_minutes=None, local_dt=None),
        },
    }

@app.get("/v1/system/endpoints")
async def system_endpoints():
    if os.getenv("ENABLE_ENDPOINTS_LIST") != "1":
        raise HTTPException(status_code=404, detail="Endpoint não disponível.")
    return {
        "endpoints": ENDPOINTS_CATALOG,
        "metadados": {
            "version": "v1",
            "ambiente": "dev",
            **_build_time_metadata(timezone=None, tz_offset_minutes=None, local_dt=None),
        },
    }

@app.get("/v1/account/status")
async def account_status(request: Request, auth=Depends(get_auth)):
    request_id = getattr(request.state, "request_id", None)
    _log(
        "info",
        "account_status_request",
        request_id=request_id,
        path=request.url.path,
        user_id=auth.get("user_id"),
    )
    plan_obj = get_user_plan(auth["user_id"])
    trial_ends_at = None
    if plan_obj.plan == "trial":
        trial_ends_at = datetime.utcfromtimestamp(plan_obj.trial_started_at + TRIAL_SECONDS).isoformat() + "Z"

    features = {
        "can_see_full_daily_analysis": plan_obj.plan != "free",
        "can_see_next_30_days": plan_obj.plan != "free",
        "can_see_personal_transits": plan_obj.plan != "free",
        "can_create_multiple_sinastries": plan_obj.plan == "premium",
    }

    return {
        "plan": plan_obj.plan,
        "trial_ends_at": trial_ends_at,
        "renews_at": None,
        "features": features,
        "account": {
            "name": None,
            "birth_date": None,
            "birth_time": None,
            "birth_city": None,
            "timezone": None,
        },
        "metadados": {
            "requested_at": datetime.utcnow().isoformat() + "Z",
            "trial_started_at": datetime.utcfromtimestamp(plan_obj.trial_started_at).isoformat() + "Z",
        },
    }


@app.post("/v1/account/plan-status")
async def account_plan_status(request: Request, auth=Depends(get_auth)):
    request_id = getattr(request.state, "request_id", None)
    _log(
        "info",
        "account_plan_status_request",
        request_id=request_id,
        path=request.url.path,
        user_id=auth.get("user_id"),
    )
    plan_obj = get_user_plan(auth["user_id"])
    trial_ends = None
    if plan_obj.plan == "trial":
        trial_ends = datetime.utcfromtimestamp(plan_obj.trial_started_at + TRIAL_SECONDS).isoformat() + "Z"

    features = {
        "full_daily": plan_obj.plan != "free",
        "personal_transits": plan_obj.plan != "free",
        "unlimited_sinastria": plan_obj.plan == "premium",
        "timeline_30_days": plan_obj.plan != "free",
    }

    return {
        "plan": plan_obj.plan,
        "trial_ends": trial_ends,
        "features": features,
    }


@app.post("/v1/synastry/compare")
async def synastry_compare(
    body: SynastryRequest,
    request: Request,
    auth=Depends(get_auth),
):
    request_id = getattr(request.state, "request_id", None)
    _log(
        "info",
        "synastry_compare_request",
        request_id=request_id,
        path=request.url.path,
        user_id=auth.get("user_id"),
    )
    try:
        def build_person(person: SynastryPerson) -> Dict[str, Any]:
            natal_dt, warnings, time_missing = parse_local_datetime_ptbr(
                person.birth_date, person.birth_time
            )
            tz_offset_minutes = _tz_offset_for(
                natal_dt,
                person.timezone,
                person.tz_offset_minutes,
                request_id=request_id,
                path=request.url.path,
            )
            chart = compute_chart(
                year=natal_dt.year,
                month=natal_dt.month,
                day=natal_dt.day,
                hour=natal_dt.hour,
                minute=natal_dt.minute,
                second=natal_dt.second,
                lat=person.lat,
                lng=person.lng,
                tz_offset_minutes=tz_offset_minutes,
                house_system=person.house_system.value,
                zodiac_type=person.zodiac_type.value,
                ayanamsa=person.ayanamsa,
            )
            return {
                "name": person.name,
                "birth_date_input": person.birth_date,
                "birth_date_local": natal_dt.date().isoformat(),
                "birth_time_input": person.birth_time,
                "birth_time_precise": not time_missing,
                "timezone": person.timezone,
                "tz_offset_minutes": tz_offset_minutes,
                "warnings": warnings,
                "chart": chart,
            }

        person_a = build_person(body.person_a)
        person_b = build_person(body.person_b)

        return {
            "person_a": person_a,
            "person_b": person_b,
            "metadados": {
                "request_id": request_id,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "synastry_compare_error",
            exc_info=True,
            extra={"request_id": request_id, "path": request.url.path},
        )
        return _json_error_response(
            request,
            status_code=500,
            error="SERVIDOR_TEMPORARIO",
            message="Tente novamente em 1 minuto",
        )

@app.get("/v1/account/plan")
async def account_plan(auth=Depends(get_auth)):
    plan_obj = get_user_plan(auth["user_id"])
    trial_started_at = int(plan_obj.trial_started_at)
    trial_ends_at = int(plan_obj.trial_started_at + TRIAL_SECONDS)
    return {
        "plan": plan_obj.plan,
        "trial_started_at": trial_started_at,
        "trial_ends_at": trial_ends_at,
        "is_trial": plan_obj.plan == "trial",
    }


@app.post("/v1/time/resolve-tz")
async def resolve_timezone(body: TimezoneResolveRequest, request: Request):
    dt = datetime(
        year=body.year,
        month=body.month,
        day=body.day,
        hour=body.hour,
        minute=body.minute,
        second=body.second,
    )
    resolved_offset = _tz_offset_for(
        dt,
        body.timezone,
        fallback_minutes=None,
        strict=body.strict_birth,
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
    )
    return {
        "tz_offset_minutes": resolved_offset,
        "metadados_tecnicos": {
            "idioma": "pt-BR",
            "fonte_traducao": "backend",
            **_build_time_metadata(
                timezone=body.timezone,
                tz_offset_minutes=resolved_offset,
                local_dt=dt,
            ),
        },
    }


@app.post("/v1/time/validate-local-datetime")
async def validate_local_datetime(body: ValidateLocalDatetimeRequest):
    result = timezone_utils.validate_local_datetime(
        body.datetime_local, body.timezone, strict=body.strict
    )
    warnings = []
    if result.warning:
        warning_message = result.warning.get("message")
        if warning_message:
            warnings.append(warning_message)
    payload = {
        "input_datetime_local": result.input_datetime.isoformat(),
        "datetime_local": result.resolved_datetime.isoformat(),
        "timezone": result.timezone,
        "tz_offset_minutes": result.tz_offset_minutes,
        "utc_datetime": result.utc_datetime.isoformat(),
        "fold": result.fold,
        "warning": result.warning,
        "datetime_local_usado": result.resolved_datetime.isoformat(),
        "datetime_utc_usado": result.utc_datetime.replace(tzinfo=None).isoformat(),
        "fold_usado": result.fold,
        "avisos": warnings,
        "metadados_tecnicos": {
            "idioma": "pt-BR",
            "fonte_traducao": "backend",
            "timezone": result.timezone,
            "tz_offset_minutes": result.tz_offset_minutes,
            "fold": result.fold,
        },
    }
    if result.adjustment_minutes:
        payload["metadados_tecnicos"]["ajuste_minutos"] = result.adjustment_minutes
    return payload

@app.post("/v1/diagnostics/ephemeris-check")
async def ephemeris_check(body: EphemerisCheckRequest, request: Request, auth=Depends(get_auth)):
    tz_offset_minutes = _tz_offset_for(
        body.datetime_local,
        body.timezone,
        fallback_minutes=None,
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
    )
    utc_dt = body.datetime_local - timedelta(minutes=tz_offset_minutes)
    local_dt = parse_local_datetime(datetime_local=body.datetime_local)
    localized = localize_with_zoneinfo(local_dt, body.timezone, None)
    utc_dt = to_utc(localized.datetime_local, localized.tz_offset_minutes)
    jd_ut = to_julian_day(utc_dt)

    chart = compute_chart(
        year=local_dt.year,
        month=local_dt.month,
        day=local_dt.day,
        hour=local_dt.hour,
        minute=local_dt.minute,
        second=local_dt.second,
        lat=body.lat,
        lng=body.lng,
        tz_offset_minutes=localized.tz_offset_minutes,
        house_system="P",
        zodiac_type="tropical",
        ayanamsa=None,
    )

    items = []
    for name, planet_id in PLANETS.items():
        result, _ = swe.calc_ut(jd_ut, planet_id)
        ref_lon = result[0] % 360.0
        chart_lon = float(chart["planets"][name]["lon"])
        delta = angle_diff(chart_lon, ref_lon)
        items.append(
            {
                "planet": name,
                "chart_lon": round(chart_lon, 6),
                "ref_lon": round(ref_lon, 6),
                "delta_deg_abs": round(delta, 6),
            }
        )

    return {
        "utc_datetime": utc_dt.isoformat(),
        "tz_offset_minutes": localized.tz_offset_minutes,
        "timezone_resolvida": localized.timezone_resolved,
        "tz_offset_minutes_usado": localized.tz_offset_minutes,
        "fold_usado": localized.fold,
        "datetime_local_usado": localized.datetime_local.isoformat(),
        "datetime_utc_usado": utc_dt.isoformat(),
        "avisos": localized.warnings,
        "items": items,
        "metadados_tecnicos": {
            "idioma": "pt-BR",
            "fonte_traducao": "backend",
            **_build_time_metadata(
                timezone=body.timezone,
                tz_offset_minutes=tz_offset_minutes,
                local_dt=body.datetime_local,
            ),
        },
    }

@app.post("/v1/insights/mercury-retrograde")
async def mercury_retrograde(
    body: MercuryRetrogradeRequest,
    request: Request,
    auth=Depends(get_auth),
):
    y, m, d = _parse_date_yyyy_mm_dd(body.target_date)
    tz_offset_minutes = _tz_offset_for(
        datetime(year=y, month=m, day=d, hour=12, minute=0, second=0),
        body.timezone,
        body.tz_offset_minutes,
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
    )

    transit_chart = compute_transits(
        target_year=y,
        target_month=m,
        target_day=d,
        lat=body.lat,
        lng=body.lng,
        tz_offset_minutes=tz_offset_minutes,
        zodiac_type=body.zodiac_type.value,
        ayanamsa=body.ayanamsa,
    )

    mercury = transit_chart["planets"]["Mercury"]
    retrograde = bool(mercury.get("retrograde"))
    speed = mercury.get("speed")

    return {
        "date": body.target_date,
        "status": "retrograde" if retrograde else "direct",
        "retrograde": retrograde,
        "speed": speed,
        "planet": "Mercury",
        "note": "Baseado na velocidade aparente da efeméride no horário local de referência.",
        "status_ptbr": "Retrógrado" if retrograde else "Direto",
        "planeta_ptbr": "Mercúrio",
        "bullets_ptbr": [
            "Revisões e checagens ganham prioridade.",
            "Comunicações pedem clareza extra.",
            "Ajustes de cronograma ajudam a manter o ritmo.",
        ],
    }

@app.post("/v1/insights/dominant-theme")
async def dominant_theme(
    body: TransitsRequest,
    request: Request,
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    natal_dt = datetime(
        year=body.natal_year,
        month=body.natal_month,
        day=body.natal_day,
        hour=body.natal_hour,
        minute=body.natal_minute,
        second=body.natal_second,
    )
    tz_offset_minutes = _tz_offset_for(
        natal_dt,
        body.timezone,
        body.tz_offset_minutes,
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
    )
    context = _build_transits_context(body, tz_offset_minutes, lang)
    aspects = context["aspects"]
    aspectos_usados = context["aspectos_usados"]
    orbes_usados = context["orbes_usados"]

    influence_counts: Dict[str, int] = {}
    for asp in aspects:
        influence = asp.get("influence", "Neutral")
        influence_counts[influence] = influence_counts.get(influence, 0) + 1

    if not influence_counts:
        return {
            "theme": "Quiet influence",
            "summary": "Poucos aspectos relevantes no período.",
            "counts": {},
            "sample_aspects": [],
            "theme_ptbr": "Influência tranquila",
            "summary_ptbr": "Poucos aspectos relevantes no período.",
            "bullets_ptbr": [
                "Clima geral mais neutro.",
                "Bom momento para ajustes finos.",
                "Atenção aos detalhes do cotidiano.",
            ],
            "sample_aspects_ptbr": [],
            "metadados_tecnicos": {
                "aspectos_usados": aspectos_usados,
                "orbes_usados": orbes_usados,
            },
        }

    dominant_influence = max(influence_counts.items(), key=lambda item: item[1])[0]
    sample_aspects = aspects[:3]
    summary_map = {
        "Intense influence": "Foco em intensidade e viradas rápidas.",
        "Challenging influence": "Período de desafios e ajustes conscientes.",
        "Fluid influence": "Fluxo mais leve e oportunidades de integração.",
    }

    return {
        "theme": dominant_influence,
        "summary": summary_map.get(dominant_influence, "Influência predominante do período."),
        "counts": influence_counts,
        "sample_aspects": sample_aspects,
        "sample_aspects_ptbr": build_aspects_ptbr(sample_aspects),
        "theme_ptbr": {
            "Intense influence": "Influência intensa",
            "Challenging influence": "Influência desafiadora",
            "Fluid influence": "Influência fluida",
        }.get(dominant_influence, "Influência predominante"),
        "summary_ptbr": summary_map.get(
            dominant_influence, "Influência predominante do período."
        ),
        "bullets_ptbr": [
            "Observe os padrões dos aspectos principais.",
            "Priorize ações alinhadas ao tom dominante.",
            "Ajuste expectativas conforme a intensidade do período.",
        ],
        "metadados_tecnicos": {
            "aspectos_usados": aspectos_usados,
            "orbes_usados": orbes_usados,
        },
    }

@app.post("/v1/insights/areas-activated")
async def areas_activated(
    body: TransitsRequest,
    request: Request,
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    natal_dt = datetime(
        year=body.natal_year,
        month=body.natal_month,
        day=body.natal_day,
        hour=body.natal_hour,
        minute=body.natal_minute,
        second=body.natal_second,
    )
    tz_offset_minutes = _tz_offset_for(
        natal_dt,
        body.timezone,
        body.tz_offset_minutes,
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
    )
    context = _build_transits_context(body, tz_offset_minutes, lang)
    aspects = context["aspects"]
    aspectos_usados = context["aspectos_usados"]
    orbes_usados = context["orbes_usados"]

    area_map = {
        "Sun": "Identidade e propósito",
        "Moon": "Emoções e segurança",
        "Mercury": "Comunicação e estudos",
        "Venus": "Relacionamentos e afeto",
        "Mars": "Ação e energia",
        "Jupiter": "Expansão e visão",
        "Saturn": "Estrutura e responsabilidade",
        "Uranus": "Mudanças e liberdade",
        "Neptune": "Inspiração e sensibilidade",
        "Pluto": "Transformação e poder pessoal",
    }

    influence_weight = {
        "Intense influence": 3,
        "Challenging influence": 2,
        "Fluid influence": 1,
    }

    if not aspects:
        return {
            "items": [
                {"area": "Identidade e propósito", "score": 50, "aspects": []},
                {"area": "Relacionamentos e afeto", "score": 45, "aspects": []},
                {"area": "Rotina e bem-estar", "score": 40, "aspects": []},
            ],
            "bullets_ptbr": [
                "Poucos aspectos exatos: tendência a estabilidade.",
                "Priorize consistência nas decisões.",
                "Atenção aos sinais sutis do cotidiano.",
            ],
            "metadados_tecnicos": {
                "aspectos_usados": aspectos_usados,
                "orbes_usados": orbes_usados,
            },
        }

    scores: Dict[str, Dict[str, Any]] = {}
    for asp in aspects:
        planet = asp.get("natal_planet")
        area = area_map.get(planet, "Tema geral")
        weight = influence_weight.get(asp.get("influence"), 1)
        scores.setdefault(area, {"area": area, "score": 0, "aspects": []})
        scores[area]["score"] += weight
        if len(scores[area]["aspects"]) < 3:
            scores[area]["aspects"].append(asp)

    items = sorted(scores.values(), key=lambda item: item["score"], reverse=True)
    items = items[:5]
    while len(items) < 3:
        items.append({"area": "Tema geral", "score": 35, "aspects": []})
    return {
        "items": items,
        "bullets_ptbr": [
            "As áreas com maior score ganham prioridade.",
            "Busque equilíbrio entre temas ativos.",
            "Use pequenas ações para ajustar o foco.",
        ],
        "metadados_tecnicos": {
            "aspectos_usados": aspectos_usados,
            "orbes_usados": orbes_usados,
        },
    }

@app.post("/v1/insights/care-suggestion")
async def care_suggestion(
    body: TransitsRequest,
    request: Request,
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    natal_dt = datetime(
        year=body.natal_year,
        month=body.natal_month,
        day=body.natal_day,
        hour=body.natal_hour,
        minute=body.natal_minute,
        second=body.natal_second,
    )
    tz_offset_minutes = _tz_offset_for(
        natal_dt,
        body.timezone,
        body.tz_offset_minutes,
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
    )
    context = _build_transits_context(body, tz_offset_minutes, lang)
    aspects = context["aspects"]

    moon = compute_moon_only(body.target_date, tz_offset_minutes=tz_offset_minutes)
    phase = _moon_phase_4(moon["phase_angle_deg"])
    sign = moon["moon_sign"]
    sign_pt = sign_to_pt(sign)

    dominant_influence = "neutral"
    if aspects:
        dominant_influence = max(
            (asp.get("influence", "neutral") for asp in aspects),
            key=lambda influence: sum(1 for asp in aspects if asp.get("influence") == influence),
        )

    suggestion_map = {
        "intense": "Priorize pausas e escolhas conscientes para evitar impulsos.",
        "challenging": "Organize tarefas e busque apoio antes de decisões grandes.",
        "supportive": "Aproveite a fluidez para avançar em projetos criativos.",
        "neutral": "Mantenha constância e foque em rotinas simples.",
        "Intense influence": "Priorize pausas e escolhas conscientes para evitar impulsos.",
        "Challenging influence": "Organize tarefas e busque apoio antes de decisões grandes.",
        "Fluid influence": "Aproveite a fluidez para avançar em projetos criativos.",
        "Neutral": "Mantenha constância e foque em rotinas simples.",
    }

    return {
        "moon_phase": phase,
        "moon_sign": sign_pt if _is_pt_br(lang) else sign,
        "theme": dominant_influence,
        "suggestion": suggestion_map.get(dominant_influence, "Mantenha o equilíbrio e a presença."),
        "suggestion_ptbr": suggestion_map.get(dominant_influence, "Mantenha o equilíbrio e a presença."),
        "bullets_ptbr": [
            "Respeite seus limites do dia.",
            "Ajustes pequenos geram consistência.",
            "Evite decisões impulsivas.",
        ],
    }

@app.post("/v1/insights/life-cycles")
async def life_cycles(
    body: TransitsRequest,
    request: Request,
    auth=Depends(get_auth),
):
    target_y, target_m, target_d = _parse_date_yyyy_mm_dd(body.target_date)
    birth = datetime(
        year=body.natal_year,
        month=body.natal_month,
        day=body.natal_day,
        hour=body.natal_hour,
        minute=body.natal_minute,
        second=body.natal_second,
    )
    target = datetime(target_y, target_m, target_d)
    age_years = (target - birth).days / 365.25

    cycles = [
        {"name": "Retorno de Saturno", "cycle_years": 29.5},
        {"name": "Retorno de Júpiter", "cycle_years": 11.86},
        {"name": "Retorno de Nodos Lunares", "cycle_years": 18.6},
    ]

    items = []
    for cycle in cycles:
        cycle_years = cycle["cycle_years"]
        nearest = round(age_years / cycle_years) * cycle_years
        delta = age_years - nearest
        status = "active" if abs(delta) < 0.5 else "out_of_window"
        items.append(
            {
                "cycle": cycle["name"],
                "approx_age_years": round(nearest, 2),
                "distance_years": round(delta, 2),
                "status": status,
                "status_ptbr": "ativo" if status == "active" else "fora_da_janela",
            }
        )

    return {
        "age_years": round(age_years, 2),
        "items": items,
        "bullets_ptbr": [
            "Ciclos indicam janelas aproximadas de ativação.",
            "Use como referência para planejamento.",
            "As datas são estimadas por proximidade.",
        ],
    }

@app.post("/v1/insights/solar-return", response_model=SolarReturnResponse)
async def solar_return(
    body: TransitsRequest,
    request: Request,
    auth=Depends(get_auth),
):
    target_y, _, _ = _parse_date_yyyy_mm_dd(body.target_date)
    natal_dt = datetime(
        year=body.natal_year,
        month=body.natal_month,
        day=body.natal_day,
        hour=body.natal_hour,
        minute=body.natal_minute,
        second=body.natal_second,
    )
    tz_offset_minutes = _tz_offset_for(
        natal_dt,
        body.timezone,
        body.tz_offset_minutes,
        strict=body.strict_timezone,
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
    )
    natal_local = parse_local_datetime(datetime_local=natal_dt)
    localized = localize_with_zoneinfo(
        natal_local, body.timezone, body.tz_offset_minutes, strict=body.strict_timezone
    )
    natal_utc = to_utc(localized.datetime_local, localized.tz_offset_minutes)
    solar_return_utc = _solar_return_datetime(
        natal_dt=natal_dt,
        target_year=target_y,
        tz_offset_minutes=localized.tz_offset_minutes,
        request=request,
        user_id=auth.get("user_id"),
    )
    solar_return_local = solar_return_utc + timedelta(minutes=localized.tz_offset_minutes)
    return SolarReturnResponse(
        target_year=target_y,
        solar_return_utc=solar_return_utc.isoformat(),
        solar_return_local=solar_return_local.isoformat(),
        timezone_resolvida=localized.timezone_resolved,
        tz_offset_minutes_usado=localized.tz_offset_minutes,
        fold_usado=localized.fold,
        datetime_local_usado=localized.datetime_local.isoformat(),
        datetime_utc_usado=natal_utc.isoformat(),
        avisos=localized.warnings,
        idioma="pt-BR",
        fonte_traducao="backend",
    )

@app.post("/v1/chart/natal")
async def natal(
    body: NatalChartRequest,
    request: Request,
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    try:
        dt = datetime(
            year=body.natal_year,
            month=body.natal_month,
            day=body.natal_day,
            hour=body.natal_hour,
            minute=body.natal_minute,
            second=body.natal_second,
        )
        tz_offset_minutes = _tz_offset_for(
            dt,
            body.timezone,
            body.tz_offset_minutes,
            strict=body.strict_timezone,
            request_id=getattr(request.state, "request_id", None),
            path=request.url.path,
        )

        lang_key = (lang or "").lower()
        cache_key = f"natal:{auth['user_id']}:{hash(body.model_dump_json())}:{lang_key}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        chart = compute_chart(
            year=body.natal_year,
            month=body.natal_month,
            day=body.natal_day,
            hour=body.natal_hour,
            minute=body.natal_minute,
            second=body.natal_second,
            lat=body.lat,
            lng=body.lng,
            tz_offset_minutes=tz_offset_minutes,
            house_system=body.house_system.value,
            zodiac_type=body.zodiac_type.value,
            ayanamsa=body.ayanamsa,
        )

        chart = _apply_sign_localization(chart, lang)
        chart_ptbr = _build_chart_ptbr(chart)
        chart.update(chart_ptbr)
        chart["metadados_tecnicos"] = {
            "idioma": "pt-BR",
            "fonte_traducao": "backend",
        }
        chart["metadados_tecnicos"].update(
            _build_time_metadata(
                timezone=body.timezone,
                tz_offset_minutes=tz_offset_minutes,
                local_dt=dt,
            )
        )
        chart["metadados_tecnicos"]["birth_time_precise"] = body.birth_time_precise

        cache.set(cache_key, chart, ttl_seconds=TTL_NATAL_SECONDS)
        return chart
    except Exception as e:
        logger.error(
            "natal_error",
            exc_info=True,
            extra={"request_id": getattr(request.state, "request_id", None), "path": request.url.path},
        )
        raise HTTPException(status_code=500, detail=f"Erro ao calcular mapa natal: {str(e)}")

@app.post("/v1/chart/distributions")
async def chart_distributions(
    body: NatalChartRequest,
    request: Request,
    auth=Depends(get_auth),
):
    try:
        dt = datetime(
            year=body.natal_year,
            month=body.natal_month,
            day=body.natal_day,
            hour=body.natal_hour,
            minute=body.natal_minute,
            second=body.natal_second,
        )
        tz_offset_minutes = _tz_offset_for(
            dt,
            body.timezone,
            body.tz_offset_minutes,
            strict=body.strict_timezone,
            request_id=getattr(request.state, "request_id", None),
            path=request.url.path,
        )
        chart = compute_chart(
            year=body.natal_year,
            month=body.natal_month,
            day=body.natal_day,
            hour=body.natal_hour,
            minute=body.natal_minute,
            second=body.natal_second,
            lat=body.lat,
            lng=body.lng,
            tz_offset_minutes=tz_offset_minutes,
            house_system=body.house_system.value,
            zodiac_type=body.zodiac_type.value,
            ayanamsa=body.ayanamsa,
        )
        payload = _distributions_payload(
            chart,
            metadata={
                **_build_time_metadata(
                timezone=body.timezone,
                tz_offset_minutes=tz_offset_minutes,
                local_dt=dt,
                ),
                "birth_time_precise": body.birth_time_precise,
            },
        )
        payload.update(
            {
                "elements": payload.get("elementos", {}),
                "modalities": payload.get("modalidades", {}),
                "houses": payload.get("casas", []),
            }
        )
        return payload
    except Exception as e:
        logger.error(
            "distributions_error",
            exc_info=True,
            extra={"request_id": getattr(request.state, "request_id", None), "path": request.url.path},
        )
        raise HTTPException(status_code=500, detail=f"Erro ao calcular distribuições: {str(e)}")

@app.post("/v1/chart/transits")
async def transits(
    body: TransitsRequest,
    request: Request,
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    y, m, d = _parse_date_yyyy_mm_dd(body.target_date)

    try:
        natal_dt = datetime(
            year=body.natal_year,
            month=body.natal_month,
            day=body.natal_day,
            hour=body.natal_hour,
            minute=body.natal_minute,
            second=body.natal_second,
        )
        tz_offset_minutes = _tz_offset_for(
            natal_dt,
            body.timezone,
            body.tz_offset_minutes,
            request_id=getattr(request.state, "request_id", None),
            path=request.url.path,
        )

        lang_key = (lang or "").lower()
        cache_key = f"transits:{auth['user_id']}:{body.target_date}:{lang_key}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        natal_chart = compute_chart(
            year=body.natal_year,
            month=body.natal_month,
            day=body.natal_day,
            hour=body.natal_hour,
            minute=body.natal_minute,
            second=body.natal_second,
            lat=body.lat,
            lng=body.lng,
            tz_offset_minutes=tz_offset_minutes,
            house_system=body.house_system.value,
            zodiac_type=body.zodiac_type.value,
            ayanamsa=body.ayanamsa,
        )

        transit_chart = compute_transits(
            target_year=y,
            target_month=m,
            target_day=d,
            lat=body.lat,
            lng=body.lng,
            tz_offset_minutes=tz_offset_minutes,
            zodiac_type=body.zodiac_type.value,
            ayanamsa=body.ayanamsa,
        )

        natal_chart = _apply_sign_localization(natal_chart, lang)
        transit_chart = _apply_sign_localization(transit_chart, lang)

        aspects_profile, aspects_config = get_aspects_profile()
        aspects = compute_transit_aspects(
            transit_planets=transit_chart["planets"],
            natal_planets=natal_chart["planets"],
            aspects=aspects_config,
        )

        moon = compute_moon_only(body.target_date, tz_offset_minutes=tz_offset_minutes)
        phase = _moon_phase_4(moon["phase_angle_deg"])
        sign = moon["moon_sign"]
        phase_label = _moon_phase_label_pt(phase)
        cosmic_weather = {
            "moon_phase": phase,
            "moon_sign": sign,
            "headline": f"Lua {phase_label} em {sign}",
            "text": _cw_text(phase, sign),
        }
        cosmic_weather = {
            "moon_phase": phase,
            "moon_sign": sign,
            "headline": f"Lua {phase} em {sign}",
            "text": _cw_text(phase, sign),
            "deg_in_sign": moon.get("deg_in_sign"),
        }
        cosmic_weather = _apply_moon_localization(cosmic_weather, lang)
        cosmic_weather["headline"] = f"Lua {phase} em {cosmic_weather['moon_sign']}"

        natal_ptbr = _build_chart_ptbr(natal_chart)
        transits_ptbr = _build_chart_ptbr(transit_chart)
        aspectos_ptbr = build_aspects_ptbr(aspects)
        cosmic_weather_ptbr = _build_cosmic_weather_ptbr(
            {**cosmic_weather, "moon_phase": phase, "moon_sign": cosmic_weather["moon_sign"]}
        )

        response = {
            "date": body.target_date,
            "cosmic_weather": cosmic_weather,
            "cosmic_weather_ptbr": cosmic_weather_ptbr,
            "natal": natal_chart,
            "natal_ptbr": natal_ptbr,
            "transits": transit_chart,
            "transits_ptbr": transits_ptbr,
            "aspects": aspects,
            "aspectos_ptbr": aspectos_ptbr,
            "areas_activated": _areas_activated(aspects, phase),
            "metadados_tecnicos": {
                "perfil_aspectos": aspects_profile,
                "birth_time_precise": body.birth_time_precise,
            },
        }

        cache.set(cache_key, response, ttl_seconds=TTL_TRANSITS_SECONDS)
        return response

    except Exception as e:
        logger.error(
            "transits_error",
            exc_info=True,
            extra={"request_id": getattr(request.state, "request_id", None), "path": request.url.path},
        )
        raise HTTPException(status_code=500, detail=f"Erro ao calcular trânsitos: {str(e)}")

@app.post("/v1/transits/live")
async def transits_live(body: TransitsLiveRequest, request: Request, auth=Depends(get_auth)):
    target_dt = body.target_datetime
    tz_offset_minutes = body.tz_offset_minutes

    if body.timezone or tz_offset_minutes is not None:
        local_dt = target_dt.replace(tzinfo=None)
    else:
        offset = target_dt.utcoffset()
        if offset is None:
            raise HTTPException(
                status_code=400,
                detail="Informe timezone IANA, tz_offset_minutes ou target_datetime com offset.",
            )
        tz_offset_minutes = int(offset.total_seconds() // 60)
        local_dt = target_dt.replace(tzinfo=None)

    resolved_offset = _tz_offset_for(
        local_dt, body.timezone, tz_offset_minutes, strict=body.strict_timezone
    )
    target_date = local_dt.strftime("%Y-%m-%d")

    try:
        transit_chart = compute_transits(
            target_year=local_dt.year,
            target_month=local_dt.month,
            target_day=local_dt.day,
            lat=body.lat,
            lng=body.lng,
            tz_offset_minutes=resolved_offset,
            zodiac_type=body.zodiac_type.value,
            ayanamsa=body.ayanamsa,
        )

        return {
            "date": target_date,
            "target_datetime": target_dt.isoformat(),
            "tz_offset_minutes": resolved_offset,
            "transits": transit_chart,
        }
    except Exception as e:
        logger.error(
            "transits_live_error",
            exc_info=True,
            extra={"request_id": getattr(request.state, "request_id", None), "path": request.url.path},
        )
        raise HTTPException(status_code=500, detail=f"Erro ao calcular trânsitos: {str(e)}")
@app.post("/v1/interpretation/natal")
async def interpretation_natal(
    body: NatalChartRequest,
    request: Request,
    auth=Depends(get_auth),
):
    dt = datetime(
        year=body.natal_year,
        month=body.natal_month,
        day=body.natal_day,
        hour=body.natal_hour,
        minute=body.natal_minute,
        second=body.natal_second,
    )
    tz_offset_minutes = _tz_offset_for(
        dt,
        body.timezone,
        body.tz_offset_minutes,
        strict=body.strict_timezone,
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
    )
    chart = compute_chart(
        year=body.natal_year,
        month=body.natal_month,
        day=body.natal_day,
        hour=body.natal_hour,
        minute=body.natal_minute,
        second=body.natal_second,
        lat=body.lat,
        lng=body.lng,
        tz_offset_minutes=tz_offset_minutes,
        house_system=body.house_system.value,
        zodiac_type=body.zodiac_type.value,
        ayanamsa=body.ayanamsa,
    )
    distributions = _distributions_payload(
        chart,
        metadata=_build_time_metadata(
            timezone=body.timezone,
            tz_offset_minutes=tz_offset_minutes,
            local_dt=dt,
        ),
    )

    planets = chart.get("planets", {})
    houses = chart.get("houses", {})
    cusps = houses.get("cusps") or []
    asc = float(houses.get("asc", 0.0))
    mc = float(houses.get("mc", 0.0))
    dsc = (asc + 180.0) % 360
    ic = (mc + 180.0) % 360

    avisos: List[str] = []
    angular_points = [asc, mc, dsc, ic]

    planet_weights: List[Dict[str, Any]] = []
    for name in PLANETS.keys():
        planet = planets.get(name)
        if not planet:
            continue
        lon = planet.get("lon")
        if lon is None:
            continue
        house = _house_for_lon(cusps, float(lon))
        angularity = min(angle_diff(float(lon), pt) for pt in angular_points)
        angular_score = 1.0 if angularity <= 5 else 0.4 if angularity <= 10 else 0.1
        house_score = 0.8 if house in {1, 4, 7, 10} else 0.4 if house in {2, 5, 8, 11} else 0.2
        weight = round(0.2 + angular_score + house_score, 2)
        planet_weights.append(
            {
                "planeta": planet_key_to_ptbr(name),
                "peso": min(weight, 1.0),
                "porque": f"Casa {house} com influência de ângulos ({angularity:.1f}°).",
            }
        )

    planet_weights.sort(key=lambda item: item["peso"], reverse=True)
    top_planets = planet_weights[:3] if planet_weights else []

    sun = planets.get("Sun", {})
    moon = planets.get("Moon", {})
    sun_sign = sign_to_ptbr(sun.get("sign", ""))
    moon_sign = sign_to_ptbr(moon.get("sign", ""))
    sun_house = _house_for_lon(cusps, float(sun.get("lon", 0.0))) if sun else None
    moon_house = _house_for_lon(cusps, float(moon.get("lon", 0.0))) if moon else None

    asc_sign = sign_to_ptbr(sign_for_longitude(asc))
    ruler = RULER_MAP.get(sign_for_longitude(asc))
    ruler_house = None
    if ruler and planets.get(ruler) and planets[ruler].get("lon") is not None:
        ruler_house = _house_for_lon(cusps, float(planets[ruler]["lon"]))
    else:
        avisos.append("Casa do regente do Ascendente indisponível.")

    sintese = [
        f"Sol em {sun_sign} aponta foco em temas de vida mais visíveis.",
        f"Lua em {moon_sign} indica estilo emocional e necessidades afetivas.",
        f"Ascendente em {asc_sign} sugere um jeito direto de se apresentar.",
    ]

    temas_principais = [
        {
            "titulo": "Foco solar",
            "porque": f"Sol em {sun_sign} na casa {sun_house}.",
        },
        {
            "titulo": "Tom emocional",
            "porque": f"Lua em {moon_sign} na casa {moon_house}.",
        },
    ]
    if ruler_house:
        temas_principais.append(
            {
                "titulo": "Estilo de ação",
                "porque": f"Regente do Ascendente em casa {ruler_house}.",
            }
        )
    else:
        temas_principais.append(
            {
                "titulo": "Estilo de ação",
                "porque": "Regente do Ascendente não disponível no momento.",
            }
        )

    payload = {
        "interpretacao": {"tipo": "heuristica", "fonte": "regras_internas"},
        "titulo": "Resumo Geral do Mapa",
        "sintese": sintese,
        "temas_principais": temas_principais,
        "planetas_com_maior_peso": top_planets,
        "distribuicao": distributions,
        "avisos": avisos,
        "interpretacao": {"tipo": "heuristica", "fonte": "regras_internas"},
        "metadados": {"version": "v1", "fonte": "regras"},
        "summary": " ".join(sintese),
        "highlights": top_planets,
        "themes": temas_principais,
    }
    payload["metadados"].update(
        _build_time_metadata(
            timezone=body.timezone,
            tz_offset_minutes=tz_offset_minutes,
            local_dt=dt,
        )
    )
    payload["metadados"]["birth_time_precise"] = body.birth_time_precise
    return payload


@app.post("/v1/transits/events", response_model=TransitEventsResponse)
async def transits_events(
    body: TransitsEventsRequest,
    request: Request,
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    request_id = getattr(request.state, "request_id", None)
    _log(
        "info",
        "transits_events_request",
        request_id=request_id,
        path=request.url.path,
        user_id=auth.get("user_id"),
    )
    try:
        natal_dt = datetime(
            year=body.natal_year,
            month=body.natal_month,
            day=body.natal_day,
            hour=body.natal_hour,
            minute=body.natal_minute,
            second=body.natal_second,
        )
        tz_offset_minutes = _tz_offset_for(
            natal_dt,
            body.timezone,
            body.tz_offset_minutes,
            strict=body.strict_timezone,
            request_id=request_id,
            path=request.url.path,
        )

        start_y, start_m, start_d = _parse_date_yyyy_mm_dd(body.range.from_)
        end_y, end_m, end_d = _parse_date_yyyy_mm_dd(body.range.to)
        start_date = datetime(year=start_y, month=start_m, day=start_d)
        end_date = datetime(year=end_y, month=end_m, day=end_d)
        if end_date < start_date:
            raise HTTPException(status_code=400, detail="Intervalo inválido: 'from' deve ser <= 'to'.")
        interval_days = (end_date - start_date).days + 1
        if interval_days > 30:
            raise HTTPException(
                status_code=400,
                detail="Intervalo máximo de 30 dias para eventos de trânsito.",
            )

        lang_key = (lang or "").lower()
        cache_key = f"transit-events:{auth['user_id']}:{hash(body.model_dump_json())}:{lang_key}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        events: List[TransitEvent] = []
        current = start_date
        first_context = None
        for _ in range(interval_days):
            date_str = current.strftime("%Y-%m-%d")
            context = _build_transits_context(
                body,
                tz_offset_minutes,
                lang,
                date_override=date_str,
                preferencias=body.preferencias,
            )
            if first_context is None:
                first_context = context
            events.extend(_build_transit_events_for_date(date_str, context))
            current += timedelta(days=1)

        events.sort(key=lambda item: (item.date_range.peak_utc, -item.impact_score))
        avisos: List[str] = []
        metadata = {
            "range": {"from": body.range.from_, "to": body.range.to},
            "perfil": (first_context or {}).get("profile", "custom"),
            "aspectos_usados": (first_context or {}).get("aspectos_usados", []),
            "orbes_usados": (first_context or {}).get("orbes_usados", {}),
            "birth_time_precise": body.birth_time_precise,
        }
        metadata.update(
            _build_time_metadata(
                timezone=body.timezone,
                tz_offset_minutes=tz_offset_minutes,
                local_dt=natal_dt,
            )
        )

        payload = TransitEventsResponse(events=events, metadados=metadata, avisos=avisos)
        cache.set(cache_key, payload.model_dump(), ttl_seconds=TTL_TRANSITS_SECONDS)
        return payload
    except HTTPException:
        raise
    except Exception:
        logger.error(
            "transits_events_error",
            exc_info=True,
            extra={"request_id": request_id, "path": request.url.path},
        )
        return _json_error_response(
            request,
            status_code=500,
            error="INTERNAL_ERROR",
            message="Tivemos um problema no servidor ao calcular os trânsitos. Tente novamente em alguns minutos.",
        )


@app.get("/v1/daily/summary")
async def daily_summary(
    request: Request,
    date: Optional[str] = None,
    timezone: Optional[str] = Query(None, description="Timezone IANA"),
    tz_offset_minutes: Optional[int] = Query(
        None, ge=-840, le=840, description="Offset manual em minutos; ignorado se timezone for enviado."
    ),
    natal_year: Optional[int] = Query(None, ge=1800, le=2100),
    natal_month: Optional[int] = Query(None, ge=1, le=12),
    natal_day: Optional[int] = Query(None, ge=1, le=31),
    natal_hour: Optional[int] = Query(None, ge=0, le=23),
    natal_minute: int = Query(0, ge=0, le=59),
    natal_second: int = Query(0, ge=0, le=59),
    lat: Optional[float] = Query(None, ge=-89.9999, le=89.9999),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    house_system: HouseSystem = Query(HouseSystem.PLACIDUS),
    zodiac_type: ZodiacType = Query(ZodiacType.TROPICAL),
    ayanamsa: Optional[str] = Query(None),
    preferencias_perfil: Optional[Literal["padrao", "custom"]] = Query(None),
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    request_id = getattr(request.state, "request_id", None)
    _log(
        "info",
        "daily_summary_request",
        request_id=request_id,
        path=request.url.path,
        user_id=auth.get("user_id"),
    )
    try:
        d = date or _now_yyyy_mm_dd()
        payload = _cosmic_weather_payload(
            d,
            timezone,
            tz_offset_minutes,
            auth["user_id"],
            lang,
            request_id=request_id,
            path=request.url.path,
        )
        headline = payload.get("headline")
        summary = _daily_summary(payload.get("moon_phase"), payload.get("moon_sign"))
        technical_aspects: List[Dict[str, Any]] = []
        areas = []
        curated = None

        if (
            natal_year
            and natal_month
            and natal_day
            and lat is not None
            and lng is not None
        ):
            hour = natal_hour if natal_hour is not None else 12
            birth_time_precise = natal_hour is not None
            natal_dt = datetime(
                year=natal_year,
                month=natal_month,
                day=natal_day,
                hour=hour,
                minute=natal_minute,
                second=natal_second,
            )
            tz_offset_minutes_resolved = _tz_offset_for(
                natal_dt,
                timezone,
                tz_offset_minutes,
                request_id=request_id,
                path=request.url.path,
            )
            preferencias = (
                PreferenciasPerfil(perfil=preferencias_perfil) if preferencias_perfil is not None else None
            )
            transits_body = TransitsRequest(
                natal_year=natal_year,
                natal_month=natal_month,
                natal_day=natal_day,
                natal_hour=hour,
                natal_minute=natal_minute,
                natal_second=natal_second,
                lat=lat,
                lng=lng,
                tz_offset_minutes=tz_offset_minutes_resolved,
                timezone=timezone,
                target_date=d,
                house_system=house_system,
                zodiac_type=zodiac_type,
                ayanamsa=ayanamsa,
                preferencias=preferencias,
                birth_time_precise=birth_time_precise,
            )
            context = _build_transits_context(
                transits_body,
                tz_offset_minutes_resolved,
                lang,
                date_override=d,
                preferencias=transits_body.preferencias,
            )
            events = _build_transit_events_for_date(d, context)
            curated = _curate_daily_events(events)
            if curated and curated.get("summary"):
                summary = curated["summary"]
            if curated and curated.get("top_event"):
                headline = curated["top_event"].copy.headline
            areas = _areas_activated(context["aspects"], payload.get("moon_phase"))
            for asp in context["aspects"][:8]:
                orb = float(asp.get("orb", 0.0))
                score = _impact_score(
                    asp.get("transit_planet"),
                    asp.get("aspect"),
                    asp.get("natal_planet"),
                    orb,
                    context.get("orb_max") or PROFILE_DEFAULT_ORB_MAX,
                )
                severity = _severity_for(score)
                technical_aspects.append(
                    {
                        "type": asp.get("aspect"),
                        "planets": [asp.get("transit_planet"), asp.get("natal_planet")],
                        "orb": round(orb, 2),
                        "strength": {"ALTA": "strong", "MEDIA": "medium", "BAIXA": "low"}.get(
                            severity, "low"
                        ),
                    }
                )
        if first_context is None:
            first_context = context
        events.extend(_build_transit_events_for_date(date_str, context))
        current += timedelta(days=1)

        def area_text(area_name: str, level: str) -> str:
            level_map = {
                "low": "mais estável",
                "medium": "em movimento",
                "high": "em alta",
                "intense": "bem intenso",
            }
            label = level_map.get(level, "em movimento")
            return f"{area_name} {label}. Ajuste expectativas e mantenha o ritmo com cuidado."

        area_lookup = {item["area"]: item for item in areas} if areas else {}
        sections = [
            {
                "id": "general",
                "title": "Clima geral",
                "text": f"{summary['tom']} {summary['gatilho']}",
                "icon": "☀️",
            },
            {
                "id": "emotions",
                "title": "Emoções",
                "text": area_text(
                    "Emoções", area_lookup.get("Emoções", {}).get("level", "medium")
                ),
                "icon": "🌙",
            },
            {
                "id": "relationships",
                "title": "Relações",
                "text": area_text(
                    "Relações", area_lookup.get("Relações", {}).get("level", "medium")
                ),
                "icon": "💞",
            },
            {
                "id": "work",
                "title": "Trabalho",
                "text": area_text(
                    "Trabalho", area_lookup.get("Trabalho", {}).get("level", "medium")
                ),
                "icon": "💼",
            },
            {
                "id": "body",
                "title": "Corpo",
                "title": "Corpo e energia",
                "text": area_text(
                    "Corpo e energia", area_lookup.get("Corpo", {}).get("level", "medium")
                ),
                "icon": "🔥",
            },
        ]

        return {
            "date": d,
            "headline": headline,
            "sections": sections,
            "technical_aspects": technical_aspects,
            "technical_base": {"aspects": technical_aspects},
            "summary": summary,
            "curated_events": curated,
        }
    except HTTPException:
        raise
    except Exception:
        logger.error(
            "daily_summary_error",
            exc_info=True,
            extra={"request_id": request_id, "path": request.url.path},
        )
        return _json_error_response(
            request,
            status_code=500,
            error="SERVIDOR_TEMPORARIO",
            message="Tente novamente em 1 minuto",
        )


@app.get("/v1/cosmic-timeline/next-7-days")
async def cosmic_timeline_next_7_days(
    request: Request,
    date: Optional[str] = None,
    timezone: Optional[str] = Query(None, description="Timezone IANA"),
    tz_offset_minutes: Optional[int] = Query(
        None, ge=-840, le=840, description="Offset manual em minutos; ignorado se timezone for enviado."
    ),
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    request_id = getattr(request.state, "request_id", None)
    _log(
        "info",
        "cosmic_timeline_next_7_days_request",
        request_id=request_id,
        path=request.url.path,
        user_id=auth.get("user_id"),
    )
    try:
        start_date = datetime.strptime(date or _now_yyyy_mm_dd(), "%Y-%m-%d").date()
        days = []
        for offset in range(7):
            target_date = start_date + timedelta(days=offset)
            date_str = target_date.strftime("%Y-%m-%d")
            payload = _cosmic_weather_payload(
                date_str,
                timezone,
                tz_offset_minutes,
                auth["user_id"],
                lang,
                request_id=request_id,
                path=request.url.path,
            )
            days.append(
                {
                    "date": date_str,
                    "headline": payload.get("headline"),
                    "icon": "🌙",
                    "tags": [payload.get("moon_sign")] if payload.get("moon_sign") else [],
                    "strength": "medium",
                }
            )
        return {"days": days}
    except HTTPException:
        raise
    except Exception:
        logger.error(
            "cosmic_timeline_next_7_days_error",
            exc_info=True,
            extra={"request_id": request_id, "path": request.url.path},
        )
        return _json_error_response(
            request,
            status_code=500,
            error="SERVIDOR_TEMPORARIO",
            message="Tente novamente em 1 minuto",
        )


@app.get("/v1/transits/next-days")
async def transits_next_days(
    request: Request,
    date: Optional[str] = None,
    days: int = Query(7, ge=1, le=30),
    timezone: Optional[str] = Query(None, description="Timezone IANA"),
    tz_offset_minutes: Optional[int] = Query(
        None, ge=-840, le=840, description="Offset manual em minutos; ignorado se timezone for enviado."
    ),
    natal_year: Optional[int] = Query(None, ge=1800, le=2100),
    natal_month: Optional[int] = Query(None, ge=1, le=12),
    natal_day: Optional[int] = Query(None, ge=1, le=31),
    natal_hour: Optional[int] = Query(None, ge=0, le=23),
    natal_minute: int = Query(0, ge=0, le=59),
    natal_second: int = Query(0, ge=0, le=59),
    lat: Optional[float] = Query(None, ge=-89.9999, le=89.9999),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    house_system: HouseSystem = Query(HouseSystem.PLACIDUS),
    zodiac_type: ZodiacType = Query(ZodiacType.TROPICAL),
    ayanamsa: Optional[str] = Query(None),
    preferencias_perfil: Optional[Literal["padrao", "custom"]] = Query(None),
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    request_id = getattr(request.state, "request_id", None)
    _log(
        "info",
        "transits_next_days_request",
        request_id=request_id,
        path=request.url.path,
        user_id=auth.get("user_id"),
    )
    try:
        start_date = datetime.strptime(date or _now_yyyy_mm_dd(), "%Y-%m-%d").date()
        items = []
        for offset in range(days):
            target_date = start_date + timedelta(days=offset)
            date_str = target_date.strftime("%Y-%m-%d")
            headline = "Dia com espaço para ajustes pequenos e consistentes."
            tags: List[str] = []
            strength = "medium"
            icon = "✨"

            if (
                natal_year
                and natal_month
                and natal_day
                and lat is not None
                and lng is not None
            ):
                hour = natal_hour if natal_hour is not None else 12
                natal_dt = datetime(
                    year=natal_year,
                    month=natal_month,
                    day=natal_day,
                    hour=hour,
                    minute=natal_minute,
                    second=natal_second,
                )
                tz_offset_minutes_resolved = _tz_offset_for(
                    natal_dt,
                    timezone,
                    tz_offset_minutes,
                    request_id=request_id,
                    path=request.url.path,
                )
                preferencias = (
                    PreferenciasPerfil(perfil=preferencias_perfil)
                    if preferencias_perfil is not None
                    else None
                )
                transits_body = TransitsRequest(
                    natal_year=natal_year,
                    natal_month=natal_month,
                    natal_day=natal_day,
                    natal_hour=hour,
                    natal_minute=natal_minute,
                    natal_second=natal_second,
                    lat=lat,
                    lng=lng,
                    tz_offset_minutes=tz_offset_minutes_resolved,
                    timezone=timezone,
                    target_date=date_str,
                    house_system=house_system,
                    zodiac_type=zodiac_type,
                    ayanamsa=ayanamsa,
                    preferencias=preferencias,
                )
                context = _build_transits_context(
                    transits_body,
                    tz_offset_minutes_resolved,
                    lang,
                    date_override=date_str,
                    preferencias=transits_body.preferencias,
                )
                events = _build_transit_events_for_date(date_str, context)
                curated = _curate_daily_events(events)
                if curated and curated.get("top_event"):
                    event = curated["top_event"]
                    headline = event.copy.headline
                    tags = event.tags or []
                    strength = _strength_from_score(event.impact_score)
                    icon = _icon_for_tags(tags)
            else:
                cw = _cosmic_weather_payload(
                    date_str,
                    timezone,
                    tz_offset_minutes,
                    auth["user_id"],
                    lang,
                    request_id=request_id,
                    path=request.url.path,
                )
                headline = cw.get("headline")
                tags = [cw.get("moon_sign")] if cw.get("moon_sign") else []
                icon = "🌙"

            items.append(
                {
                    "date": date_str,
                    "headline": headline,
                    "tags": tags,
                    "icon": icon,
                    "strength": strength,
                }
            )

        return {"days": items}
    except HTTPException:
        raise
    except Exception:
        logger.error(
            "transits_next_days_error",
            exc_info=True,
            extra={"request_id": request_id, "path": request.url.path},
        )
        return _json_error_response(
            request,
            status_code=500,
            error="SERVIDOR_TEMPORARIO",
            message="Tente novamente em 1 minuto",
        )


@app.get("/v1/transits/personal-today")
async def transits_personal_today(
    request: Request,
    date: Optional[str] = None,
    timezone: Optional[str] = Query(None, description="Timezone IANA"),
    tz_offset_minutes: Optional[int] = Query(
        None, ge=-840, le=840, description="Offset manual em minutos; ignorado se timezone for enviado."
    ),
    natal_year: int = Query(..., ge=1800, le=2100),
    natal_month: int = Query(..., ge=1, le=12),
    natal_day: int = Query(..., ge=1, le=31),
    natal_hour: Optional[int] = Query(None, ge=0, le=23),
    natal_minute: int = Query(0, ge=0, le=59),
    natal_second: int = Query(0, ge=0, le=59),
    lat: float = Query(..., ge=-89.9999, le=89.9999),
    lng: float = Query(..., ge=-180, le=180),
    house_system: HouseSystem = Query(HouseSystem.PLACIDUS),
    zodiac_type: ZodiacType = Query(ZodiacType.TROPICAL),
    ayanamsa: Optional[str] = Query(None),
    preferencias_perfil: Optional[Literal["padrao", "custom"]] = Query(None),
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    request_id = getattr(request.state, "request_id", None)
    _log(
        "info",
        "transits_personal_today_request",
        request_id=request_id,
        path=request.url.path,
        user_id=auth.get("user_id"),
    )
    try:
        d = date or _now_yyyy_mm_dd()
        hour = natal_hour if natal_hour is not None else 12
        natal_dt = datetime(
            year=natal_year,
            month=natal_month,
            day=natal_day,
            hour=hour,
            minute=natal_minute,
            second=natal_second,
        )
        tz_offset_minutes_resolved = _tz_offset_for(
            natal_dt,
            timezone,
            tz_offset_minutes,
            request_id=request_id,
            path=request.url.path,
        )
        preferencias = PreferenciasPerfil(perfil=preferencias_perfil) if preferencias_perfil else None
        transits_body = TransitsRequest(
            natal_year=natal_year,
            natal_month=natal_month,
            natal_day=natal_day,
            natal_hour=hour,
            natal_minute=natal_minute,
            natal_second=natal_second,
            lat=lat,
            lng=lng,
            tz_offset_minutes=tz_offset_minutes_resolved,
            timezone=timezone,
            target_date=d,
            house_system=house_system,
            zodiac_type=zodiac_type,
            ayanamsa=ayanamsa,
            preferencias=preferencias,
        )
        context = _build_transits_context(
            transits_body,
            tz_offset_minutes_resolved,
            lang,
            date_override=d,
            preferencias=transits_body.preferencias,
        )
        events = _build_transit_events_for_date(d, context)

        area_map = {
            "Sun": "identidade",
            "Moon": "emoções",
            "Mercury": "comunicação",
            "Venus": "relacionamentos",
            "Mars": "trabalho",
            "Jupiter": "expansão",
            "Saturn": "responsabilidade",
            "Uranus": "mudanças",
            "Neptune": "sensibilidade",
            "Pluto": "transformação",
        }

        personal_transits = []
        for event in events[:8]:
            personal_transits.append(
                {
                    "type": event.aspecto,
                    "transiting_planet": event.transitando,
                    "natal_point": event.alvo,
                    "orb": event.orb_graus,
                    "area": area_map.get(event.alvo, "tema geral"),
                    "strength": _strength_from_score(event.impact_score),
                    "short_text": event.copy.mecanica,
                }
            )

        return {
            "date": d,
            "personal_transits": personal_transits,
            "metadados": {
                "birth_time_precise": natal_hour is not None,
                **_build_time_metadata(
                    timezone=timezone,
                    tz_offset_minutes=tz_offset_minutes_resolved,
                    local_dt=natal_dt,
                ),
            },
        }
    except HTTPException:
        raise
    except Exception:
        logger.error(
            "transits_personal_today_error",
            exc_info=True,
            extra={"request_id": request_id, "path": request.url.path},
        )
        return _json_error_response(
            request,
            status_code=500,
            error="SERVIDOR_TEMPORARIO",
            message="Tente novamente em 1 minuto",
        )


@app.get("/v1/revolution-solar/current-year")
async def revolution_solar_current_year(
    request: Request,
    year: int = Query(2026, ge=1800, le=2100),
    natal_year: int = Query(..., ge=1800, le=2100),
    natal_month: int = Query(..., ge=1, le=12),
    natal_day: int = Query(..., ge=1, le=31),
    natal_hour: Optional[int] = Query(None, ge=0, le=23),
    natal_minute: int = Query(0, ge=0, le=59),
    natal_second: int = Query(0, ge=0, le=59),
    lat: float = Query(..., ge=-89.9999, le=89.9999),
    lng: float = Query(..., ge=-180, le=180),
    timezone: Optional[str] = Query(None, description="Timezone IANA"),
    tz_offset_minutes: Optional[int] = Query(None, ge=-840, le=840),
    house_system: HouseSystem = Query(HouseSystem.PLACIDUS),
    zodiac_type: ZodiacType = Query(ZodiacType.TROPICAL),
    ayanamsa: Optional[str] = Query(None),
    auth=Depends(get_auth),
):
    request_id = getattr(request.state, "request_id", None)
    _log(
        "info",
        "revolution_solar_current_year_request",
        request_id=request_id,
        path=request.url.path,
        user_id=auth.get("user_id"),
    )
    try:
        hour = natal_hour if natal_hour is not None else 12
        natal_dt = datetime(
            year=natal_year,
            month=natal_month,
            day=natal_day,
            hour=hour,
            minute=natal_minute,
            second=natal_second,
        )
        tz_offset_minutes_resolved = _tz_offset_for(
            natal_dt,
            timezone,
            tz_offset_minutes,
            request_id=request_id,
            path=request.url.path,
        )
        prefs = SolarReturnPreferencias(perfil="padrao")
        aspectos_habilitados, orbes, _, _ = _apply_solar_return_profile(prefs)
        inputs = SolarReturnInputs(
            natal_date=natal_dt,
            natal_lat=lat,
            natal_lng=lng,
            natal_timezone=timezone or "UTC",
            target_year=year,
            target_lat=lat,
            target_lng=lng,
            target_timezone=timezone or "UTC",
            house_system=house_system.value,
            zodiac_type=zodiac_type.value,
            ayanamsa=ayanamsa,
            aspectos_habilitados=aspectos_habilitados,
            orbes=orbes,
            engine=(os.getenv("SOLAR_RETURN_ENGINE") or "v1").lower(),
            tz_offset_minutes=tz_offset_minutes_resolved,
        )
        payload = compute_solar_return_payload(inputs)
        sr_chart = payload.get("mapa_revolucao", {})
        cusps = sr_chart.get("casas", {}).get("cusps") if sr_chart else None
        saturn_lon = sr_chart.get("planetas", {}).get("Saturn", {}).get("lon") if sr_chart else None
        saturn_house = _house_for_lon(cusps, float(saturn_lon)) if cusps and saturn_lon else None
        year_title = "Seu ano é de construção"
        if saturn_house:
            year_title = f"Seu ano é de construção (Saturno casa {saturn_house})"

        areas = payload.get("areas_ativadas", []) or []
        key_themes = [item.get("area") for item in areas[:3] if item.get("area")]
        strengths = [item.get("titulo") for item in payload.get("destaques", [])[:2] if item.get("titulo")]
        challenges = [item.get("alerta") for item in payload.get("destaques", [])[:2] if item.get("alerta")]

        return {
            "year_title": year_title,
            "key_themes": key_themes or ["carreira", "saúde", "relacionamentos"],
            "strengths": strengths or ["Vênus bem aspectada: harmonia afetiva"],
            "challenges": challenges or ["Marte em tensão: impulsividade pede cuidado"],
            "progression": "Progressão secundária: Lua em casa 10 (foco profissional)",
            "lunar_return": "Próxima lunação retorna à casa 4 (família)",
            "timeline_30_days": [],
        }
    except HTTPException:
        raise
    except Exception:
        logger.error(
            "revolution_solar_current_year_error",
            exc_info=True,
            extra={"request_id": request_id, "path": request.url.path},
        )
        return _json_error_response(
            request,
            status_code=500,
            error="SERVIDOR_TEMPORARIO",
            message="Tente novamente em 1 minuto",
        )


@app.get("/v1/moon/timeline", response_model=CosmicWeatherRangeResponse)
async def moon_timeline(
    request: Request,
    from_: Optional[str] = Query(None, alias="from", description="Data inicial no formato YYYY-MM-DD"),
    to: Optional[str] = Query(None, description="Data final no formato YYYY-MM-DD"),
    timezone: Optional[str] = Query(None, description="Timezone IANA"),
    tz_offset_minutes: Optional[int] = Query(
        None, ge=-840, le=840, description="Offset manual em minutos; ignorado se timezone for enviado."
    ),
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    request_id = getattr(request.state, "request_id", None)
    _log(
        "info",
        "moon_timeline_request",
        request_id=request_id,
        path=request.url.path,
        user_id=auth.get("user_id"),
    )
    try:
        return await cosmic_weather_range(
            request=request,
            from_=from_,
            to=to,
            timezone=timezone,
            tz_offset_minutes=tz_offset_minutes,
            lang=lang,
            auth=auth,
        )
    except HTTPException:
        raise
    except Exception:
        logger.error(
            "moon_timeline_error",
            exc_info=True,
            extra={"request_id": request_id, "path": request.url.path},
        )
        return _json_error_response(
            request,
            status_code=500,
            error="SERVIDOR_TEMPORARIO",
            message="Tente novamente em 1 minuto",
        )


@app.get("/v1/cosmic-weather", response_model=CosmicWeatherResponse)
async def cosmic_weather(
    request: Request,
    date: Optional[str] = None,
    timezone: Optional[str] = Query(None, description="Timezone IANA"),
    tz_offset_minutes: Optional[int] = Query(
        None, ge=-840, le=840, description="Offset manual em minutos; ignorado se timezone for enviado."
    ),
    natal_year: Optional[int] = Query(None, ge=1800, le=2100),
    natal_month: Optional[int] = Query(None, ge=1, le=12),
    natal_day: Optional[int] = Query(None, ge=1, le=31),
    natal_hour: Optional[int] = Query(None, ge=0, le=23),
    natal_minute: int = Query(0, ge=0, le=59),
    natal_second: int = Query(0, ge=0, le=59),
    lat: Optional[float] = Query(None, ge=-89.9999, le=89.9999),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    house_system: HouseSystem = Query(HouseSystem.PLACIDUS),
    zodiac_type: ZodiacType = Query(ZodiacType.TROPICAL),
    ayanamsa: Optional[str] = Query(None),
    preferencias_perfil: Optional[Literal["padrao", "custom"]] = Query(None),
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    d = date or _now_yyyy_mm_dd()
    payload = _cosmic_weather_payload(
        d,
        timezone,
        tz_offset_minutes,
        auth["user_id"],
        lang,
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
    )
    if natal_year and natal_month and natal_day and natal_hour is not None and lat is not None and lng is not None:
        natal_dt = datetime(
            year=natal_year,
            month=natal_month,
            day=natal_day,
            hour=natal_hour,
            minute=natal_minute,
            second=natal_second,
        )
        tz_offset_minutes_resolved = _tz_offset_for(
            natal_dt,
            timezone,
            tz_offset_minutes,
            request_id=getattr(request.state, "request_id", None),
            path=request.url.path,
        )
        preferencias = (
            PreferenciasPerfil(perfil=preferencias_perfil) if preferencias_perfil is not None else None
        )
        transits_body = TransitsRequest(
            natal_year=natal_year,
            natal_month=natal_month,
            natal_day=natal_day,
            natal_hour=natal_hour,
            natal_minute=natal_minute,
            natal_second=natal_second,
            lat=lat,
            lng=lng,
            tz_offset_minutes=tz_offset_minutes_resolved,
            timezone=timezone,
            target_date=d,
            house_system=house_system,
            zodiac_type=zodiac_type,
            ayanamsa=ayanamsa,
            preferencias=preferencias,
        )
        context = _build_transits_context(
            transits_body,
            tz_offset_minutes_resolved,
            lang,
            date_override=d,
            preferencias=transits_body.preferencias,
        )
        events = _build_transit_events_for_date(d, context)
        curated = _curate_daily_events(events)
        payload.update(curated)
    return CosmicWeatherResponse(**payload)


@app.get("/v1/cosmic-weather/range", response_model=CosmicWeatherRangeResponse)
async def cosmic_weather_range(
    request: Request,
    from_: Optional[str] = Query(None, alias="from", description="Data inicial no formato YYYY-MM-DD"),
    to: Optional[str] = Query(None, description="Data final no formato YYYY-MM-DD"),
    timezone: Optional[str] = Query(None, description="Timezone IANA"),
    tz_offset_minutes: Optional[int] = Query(
        None, ge=-840, le=840, description="Offset manual em minutos; ignorado se timezone for enviado."
    ),
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    default_start = datetime.utcnow().date()
    default_end = default_start + timedelta(days=6)
    if from_ is None:
        from_ = default_start.strftime("%Y-%m-%d")
    if to is None:
        to = default_end.strftime("%Y-%m-%d")

    if timezone:
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError:
            raise HTTPException(
                status_code=422,
                detail="Invalid timezone. Use an IANA timezone like America/Sao_Paulo.",
            )
    start_y, start_m, start_d = _parse_date_yyyy_mm_dd(from_)
    end_y, end_m, end_d = _parse_date_yyyy_mm_dd(to)

    start_date = datetime(year=start_y, month=start_m, day=start_d)
    end_date = datetime(year=end_y, month=end_m, day=end_d)

    if end_date < start_date:
        raise HTTPException(status_code=400, detail="Parâmetro 'from' deve ser anterior ou igual a 'to'.")

    interval_days = (end_date - start_date).days + 1
    if interval_days > 90:
        raise HTTPException(
            status_code=422,
            detail="Range too large. Max 90 days. Use smaller windows.",
        )

    _log(
        "info",
        "cosmic_weather_range_request",
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
        status=200,
        latency_ms=None,
        user_id=auth.get("user_id"),
    )

    items: List[CosmicWeatherResponse] = []
    items_ptbr: List[Dict[str, Any]] = []
    current = start_date
    for _ in range(interval_days):
        date_str = current.strftime("%Y-%m-%d")
        payload = _cosmic_weather_payload(
            date_str,
            timezone,
            tz_offset_minutes,
            auth["user_id"],
            lang,
            request_id=getattr(request.state, "request_id", None),
            path=request.url.path,
        )
        items.append(CosmicWeatherResponse(**payload))
        items_ptbr.append(
            {
                **payload,
                **_build_cosmic_weather_ptbr(payload),
                "headline_ptbr": payload.get("headline"),
                "resumo_ptbr": payload.get("text"),
            }
        )
        current += timedelta(days=1)

    return CosmicWeatherRangeResponse(from_=from_, to=to, items=items, items_ptbr=items_ptbr)

@app.post("/v1/chart/render-data")
async def render_data(
    body: RenderDataRequest,
    request: Request,
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    dt = datetime(
        year=body.year,
        month=body.month,
        day=body.day,
        hour=body.hour,
        minute=body.minute,
        second=body.second,
    )
    tz_offset_minutes = _tz_offset_for(
        dt,
        body.timezone,
        body.tz_offset_minutes,
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
    )

    lang_key = (lang or "").lower()
    cache_key = f"render:{auth['user_id']}:{hash(body.model_dump_json())}:{lang_key}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    natal = compute_chart(
        year=body.year,
        month=body.month,
        day=body.day,
        hour=body.hour,
        minute=body.minute,
        second=body.second,
        lat=body.lat,
        lng=body.lng,
        tz_offset_minutes=tz_offset_minutes,
        house_system=body.house_system.value,
        zodiac_type=body.zodiac_type.value,
        ayanamsa=body.ayanamsa,
    )
    natal = _apply_sign_localization(natal, lang)

    cusps = natal.get("houses", {}).get("cusps")
    if not cusps or len(cusps) < 12:
        raise HTTPException(status_code=500, detail="Cálculo não retornou houses.cusps (12 valores).")

    houses = []
    for i in range(12):
        start = float(cusps[i])
        end = float(cusps[(i + 1) % 12])
        if end < start:
            end += 360.0
        houses.append({"house": i + 1, "start_deg": start, "end_deg": end})

    planets = []
    # seu compute_chart retorna planets como dict -> converte em lista útil pro front
    for name, p in natal.get("planets", {}).items():
        planets.append({
            "name": name,
            "sign": p.get("sign"),
            "sign_pt": p.get("sign_pt"),
            "deg_in_sign": p.get("deg_in_sign"),
            "angle_deg": p.get("lon"),
        })

    planetas_ptbr = []
    for planet in planets:
        name_pt = planet_key_to_ptbr(planet.get("name", ""))
        sign_pt = sign_to_ptbr(planet.get("sign", ""))
        deg_in_sign = float(planet.get("deg_in_sign") or 0.0)
        planetas_ptbr.append(
            {
                **planet,
                "nome_ptbr": name_pt,
                "signo_ptbr": sign_pt,
                "grau_formatado_ptbr": format_position_ptbr(deg_in_sign, sign_pt),
            }
        )

    zodiac = ZODIAC_SIGNS_PT

    casas_ptbr = [
        {
            "house": house["house"],
            "label_ptbr": (
                f"Casa {house['house']}: "
                f"{format_position_ptbr(float(house['start_deg']) % 30, sign_to_ptbr(sign_for_longitude(float(house['start_deg']))))}"
                f" → {format_position_ptbr(float(house['end_deg']) % 30, sign_to_ptbr(sign_for_longitude(float(house['end_deg']))))}"
            ),
        }
        for house in houses
    ]

    _, aspects_config = get_aspects_profile()
    raw_aspects = compute_transit_aspects(
        transit_planets=natal.get("planets", {}),
        natal_planets=natal.get("planets", {}),
        aspects=aspects_config,
    )
    seen_pairs = set()
    dominant_aspects = []
    for asp in raw_aspects:
        t_name = asp.get("transit_planet")
        n_name = asp.get("natal_planet")
        if not t_name or not n_name or t_name == n_name:
            continue
        pair_key = tuple(sorted([t_name, n_name]))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        dominant_aspects.append(
            {
                "planets": [t_name, n_name],
                "aspect": asp.get("aspect"),
                "orb": asp.get("orb"),
                "influence": asp.get("influence"),
            }
        )
    dominant_aspects = dominant_aspects[:5]

    resp = {
        "zodiac": zodiac,
        "houses": houses,
        "planets": planets,
        "planetas_ptbr": planetas_ptbr,
        "casas_ptbr": casas_ptbr,
        "dominant_aspects": dominant_aspects,
        "premium_aspects": [] if is_trial_or_premium(auth["plan"]) else None,
    }

    cache.set(cache_key, resp, ttl_seconds=TTL_RENDER_SECONDS)
    return resp


@app.post("/v1/solar-return/calculate")
async def solar_return_calculate(
    body: SolarReturnRequest,
    request: Request,
    auth=Depends(get_auth),
):
    try:
        ZoneInfo(body.natal.timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(
            status_code=422,
            detail="Timezone natal inválido. Use um timezone IANA (ex.: America/Sao_Paulo).",
        )

    target_timezone = body.alvo.timezone or body.natal.timezone
    try:
        ZoneInfo(target_timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(
            status_code=422,
            detail="Timezone do alvo inválido. Use um timezone IANA (ex.: America/Sao_Paulo).",
        )

    try:
        natal_dt, warnings, natal_time_missing = parse_local_datetime_ptbr(
            body.natal.data, body.natal.hora
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="Data natal inválida. Use YYYY-MM-DD.")

    prefs = body.preferencias or SolarReturnPreferencias(perfil="padrao")
    engine = (os.getenv("SOLAR_RETURN_ENGINE") or "v1").lower()
    if engine not in ("v1", "v2"):
        engine = "v1"

    aspectos_habilitados, orbes, _, _ = _apply_solar_return_profile(prefs)
    inputs = SolarReturnInputs(
        natal_date=natal_dt,
        natal_lat=body.natal.local.lat,
        natal_lng=body.natal.local.lon,
        natal_timezone=body.natal.timezone,
        target_year=body.alvo.ano,
        target_lat=body.alvo.local.lat,
        target_lng=body.alvo.local.lon,
        target_timezone=target_timezone,
        house_system=prefs.sistema_casas.value if hasattr(prefs.sistema_casas, "value") else prefs.sistema_casas,
        zodiac_type=prefs.zodiaco.value if hasattr(prefs.zodiaco, "value") else prefs.zodiaco,
        ayanamsa=prefs.ayanamsa,
        aspectos_habilitados=aspectos_habilitados,
        orbes=orbes,
        engine=engine,  # type: ignore[arg-type]
        window_days=prefs.janela_dias,
        step_hours=prefs.passo_horas,
        max_iter=prefs.max_iteracoes,
        tolerance_degrees=prefs.tolerancia_graus,
        tz_offset_minutes=None,
        natal_time_missing=natal_time_missing,
    )

    try:
        payload = compute_solar_return_payload(inputs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if engine == "v2" and os.getenv("SOLAR_RETURN_COMPARE"):
        try:
            v1_inputs = replace(inputs, engine="v1")
            v1_payload = compute_solar_return_payload(v1_inputs)
            _log(
                "info",
                "solar_return_compare",
                request_id=getattr(request.state, "request_id", None),
                path=request.url.path,
                status=200,
                latency_ms=None,
                user_id=auth.get("user_id"),
                diff_deg=abs(
                    payload["metadados_tecnicos"]["delta_longitude_graus"]
                    - v1_payload["metadados_tecnicos"]["delta_longitude_graus"]
                ),
            )
        except Exception:
            logger.warning(
                "solar_return_compare_failed",
                extra={"request_id": getattr(request.state, "request_id", None)},
            )

    _log(
        "info",
        "solar_return_request",
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
        status=200,
        latency_ms=None,
        user_id=auth.get("user_id"),
        engine=payload["metadados_tecnicos"]["engine"],
        metodo_refino=payload["metadados_tecnicos"]["metodo_refino"],
        iteracoes=payload["metadados_tecnicos"]["iteracoes"],
        delta_longitude=payload["metadados_tecnicos"]["delta_longitude_graus"],
    )

    if warnings:
        payload["warnings"] = warnings

    return payload


@app.post("/v1/solar-return/overlay")
async def solar_return_overlay(
    body: SolarReturnOverlayRequest,
    request: Request,
    auth=Depends(get_auth),
):
    try:
        ZoneInfo(body.natal.timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(
            status_code=422,
            detail="Timezone natal inválido. Use um timezone IANA (ex.: America/Sao_Paulo).",
        )

    target_timezone = body.alvo.timezone or body.natal.timezone
    try:
        ZoneInfo(target_timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(
            status_code=422,
            detail="Timezone do alvo inválido. Use um timezone IANA (ex.: America/Sao_Paulo).",
        )

    try:
        natal_dt, warnings, time_missing = parse_local_datetime_ptbr(body.natal.data, body.natal.hora)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="Data natal inválida. Use YYYY-MM-DD.")
    avisos = list(warnings)
    if time_missing:
        avisos.append("Hora natal ausente: assumindo 12:00 local.")

    localized = localize_with_zoneinfo(
        natal_dt, body.natal.timezone, None, strict=False
    )
    avisos.extend(localized.warnings)
    natal_offset = localized.tz_offset_minutes

    rs_reference = body.rs or SolarReturnOverlayReference(year=body.alvo.ano)
    if rs_reference.solar_return_utc:
        parsed = datetime.fromisoformat(rs_reference.solar_return_utc.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            solar_return_utc = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            solar_return_utc = parsed
    else:
        solar_return_utc = _solar_return_datetime(
            natal_dt=natal_dt,
            target_year=rs_reference.year or body.alvo.ano,
            tz_offset_minutes=natal_offset,
            request=request,
            user_id=auth.get("user_id"),
        )

    target_tzinfo = ZoneInfo(target_timezone)
    solar_return_local_aware = solar_return_utc.replace(tzinfo=timezone.utc).astimezone(target_tzinfo)
    solar_return_local = solar_return_local_aware.replace(tzinfo=None)
    target_offset = int(solar_return_local_aware.utcoffset().total_seconds() // 60)

    prefs = body.preferencias or SolarReturnPreferencias(perfil="padrao")
    aspectos_habilitados, orbes, _, perfil = _apply_solar_return_profile(prefs)

    natal_chart = compute_chart(
        year=natal_dt.year,
        month=natal_dt.month,
        day=natal_dt.day,
        hour=natal_dt.hour,
        minute=natal_dt.minute,
        second=natal_dt.second,
        lat=body.natal.local.lat,
        lng=body.natal.local.lon,
        tz_offset_minutes=natal_offset,
        house_system=prefs.sistema_casas.value if hasattr(prefs.sistema_casas, "value") else prefs.sistema_casas,
        zodiac_type=prefs.zodiaco.value if hasattr(prefs.zodiaco, "value") else prefs.zodiaco,
        ayanamsa=prefs.ayanamsa,
    )

    rs_chart = compute_chart(
        year=solar_return_local.year,
        month=solar_return_local.month,
        day=solar_return_local.day,
        hour=solar_return_local.hour,
        minute=solar_return_local.minute,
        second=solar_return_local.second,
        lat=body.alvo.local.lat,
        lng=body.alvo.local.lon,
        tz_offset_minutes=target_offset,
        house_system=prefs.sistema_casas.value if hasattr(prefs.sistema_casas, "value") else prefs.sistema_casas,
        zodiac_type=prefs.zodiaco.value if hasattr(prefs.zodiaco, "value") else prefs.zodiaco,
        ayanamsa=prefs.ayanamsa,
    )

    aspects_config, aspectos_usados, orbes_usados = resolve_aspects_config(
        aspectos_habilitados,
        orbes,
    )
    aspects = compute_transit_aspects(
        transit_planets=rs_chart["planets"],
        natal_planets=natal_chart["planets"],
        aspects=aspects_config,
    )
    aspectos_rs_x_natal = [
        {
            "transitando": planet_key_to_ptbr(item["transit_planet"]),
            "alvo": planet_key_to_ptbr(item["natal_planet"]),
            "aspecto": aspect_to_ptbr(item["aspect"]),
            "orb_graus": float(item["orb"]),
        }
        for item in aspects
    ]

    rs_em_casas_natais = [
        {
            "planeta_rs": planet_key_to_ptbr(name),
            "casa_natal": _house_for_lon(natal_chart.get("houses", {}).get("cusps", []), data["lon"]),
        }
        for name, data in rs_chart.get("planets", {}).items()
    ]
    natal_em_casas_rs = [
        {
            "planeta_natal": planet_key_to_ptbr(name),
            "casa_rs": _house_for_lon(rs_chart.get("houses", {}).get("cusps", []), data["lon"]),
        }
        for name, data in natal_chart.get("planets", {}).items()
    ]

    metadados = {
        "perfil": perfil,
        "aspectos_usados": aspectos_usados,
        "orbes_usados": orbes_usados,
    }
    metadados.update(
        _build_time_metadata(
            timezone=target_timezone,
            tz_offset_minutes=target_offset,
            local_dt=solar_return_local,
            avisos=avisos,
        )
    )

    return {
        "rs_em_casas_natais": rs_em_casas_natais,
        "natal_em_casas_rs": natal_em_casas_rs,
        "aspectos_rs_x_natal": aspectos_rs_x_natal,
        "avisos": avisos,
        "metadados": metadados,
    }


@app.post("/v1/solar-return/timeline")
async def solar_return_timeline(
    body: SolarReturnTimelineRequest,
    request: Request,
    auth=Depends(get_auth),
):
    try:
        ZoneInfo(body.natal.timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(
            status_code=422,
            detail="Timezone natal inválido. Use um timezone IANA (ex.: America/Sao_Paulo).",
        )

    try:
        natal_dt, warnings, time_missing = parse_local_datetime_ptbr(body.natal.data, body.natal.hora)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="Data natal inválida. Use YYYY-MM-DD.")
    avisos = list(warnings)
    if time_missing:
        avisos.append("Hora natal ausente: assumindo 12:00 local.")

    localized = localize_with_zoneinfo(
        natal_dt, body.natal.timezone, None, strict=False
    )
    avisos.extend(localized.warnings)
    natal_offset = localized.tz_offset_minutes

    prefs = body.preferencias or SolarReturnPreferencias(perfil="padrao")
    aspectos_habilitados, orbes, orb_max, perfil = _apply_solar_return_profile(prefs)

    natal_chart = compute_chart(
        year=natal_dt.year,
        month=natal_dt.month,
        day=natal_dt.day,
        hour=natal_dt.hour,
        minute=natal_dt.minute,
        second=natal_dt.second,
        lat=body.natal.local.lat,
        lng=body.natal.local.lon,
        tz_offset_minutes=natal_offset,
        house_system=prefs.sistema_casas.value if hasattr(prefs.sistema_casas, "value") else prefs.sistema_casas,
        zodiac_type=prefs.zodiaco.value if hasattr(prefs.zodiaco, "value") else prefs.zodiaco,
        ayanamsa=prefs.ayanamsa,
    )

    targets = {
        "Sol": natal_chart["planets"]["Sun"]["lon"],
        "Lua": natal_chart["planets"]["Moon"]["lon"],
        "ASC": natal_chart["houses"]["asc"],
        "MC": natal_chart["houses"]["mc"],
    }
    aspect_angles = {
        "conjunction": {"label": "Conjunção", "angle": 0},
        "sextile": {"label": "Sextil", "angle": 60},
        "square": {"label": "Quadratura", "angle": 90},
        "trine": {"label": "Trígono", "angle": 120},
        "opposition": {"label": "Oposição", "angle": 180},
    }

    start_date = datetime(body.year, 1, 1)
    end_date = datetime(body.year, 12, 31)
    current = start_date
    items = []
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        transit_chart = compute_transits(
            target_year=current.year,
            target_month=current.month,
            target_day=current.day,
            lat=body.natal.local.lat,
            lng=body.natal.local.lon,
            tz_offset_minutes=natal_offset,
            zodiac_type=prefs.zodiaco.value if hasattr(prefs.zodiaco, "value") else prefs.zodiaco,
            ayanamsa=prefs.ayanamsa,
        )
        sun_lon = transit_chart["planets"]["Sun"]["lon"]
        for alvo, natal_lon in targets.items():
            separation = angle_diff(sun_lon, natal_lon)
            for aspecto_key, aspect_info in aspect_angles.items():
                orb = abs(separation - aspect_info["angle"])
                if orb <= orb_max:
                    score = _impact_score(
                        "Sun",
                        aspecto_key,
                        alvo if alvo in TARGET_WEIGHTS else "Sun",
                        orb,
                        orb_max,
                    )
                    items.append(
                        {
                            "start": (current - timedelta(days=1)).strftime("%Y-%m-%d"),
                            "peak": date_str,
                            "end": (current + timedelta(days=1)).strftime("%Y-%m-%d"),
                            "method": "solar_aspects",
                            "trigger": f"Sol em {aspect_info['label']} com {alvo}",
                            "tags": ["Ano", "Direção", "Ajuste"],
                            "score": round(score, 2),
                        }
                    )
        current += timedelta(days=1)

    items.sort(key=lambda item: item["peak"])
    return {
        "year_timeline": items,
        "avisos": avisos,
        "metadados": {
            "perfil": perfil,
            "aspectos_usados": aspectos_habilitados or [],
            "orbes_usados": orbes or {},
            "timezone_usada": body.natal.timezone,
            "tz_offset_minutes": natal_offset,
        },
    }

@app.post("/v1/ai/cosmic-chat")
async def cosmic_chat(body: CosmicChatRequest, request: Request, auth=Depends(get_auth)):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY não configurada no servidor.")

    language = body.language or "pt-BR"
    tone = body.tone or "calmo, adulto, tecnológico"

    try:
        client = OpenAI(api_key=api_key)

        messages = build_cosmic_chat_messages(
            user_question=body.user_question,
            astro_payload=body.astro_payload,
            tone=tone,
            language=language,
        )

        max_tokens_free = int(os.getenv("OPENAI_MAX_TOKENS_FREE", "600"))
        max_tokens_paid = int(os.getenv("OPENAI_MAX_TOKENS_PAID", "1100"))
        max_tokens = max_tokens_free if auth["plan"] == "free" else max_tokens_paid

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )

        return {
            "response": response.choices[0].message.content,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            "metadados_tecnicos": {
                "idioma": "pt-BR",
                "fonte_traducao": "backend",
                **_build_time_metadata(timezone=None, tz_offset_minutes=None, local_dt=None),
            },
        }

    except Exception as e:
        logger.error(
            "cosmic_chat_error",
            exc_info=True,
            extra={"request_id": getattr(request.state, "request_id", None), "path": request.url.path},
        )
        raise HTTPException(status_code=500, detail=f"Erro no processamento de IA: {str(e)}")


@app.get("/v1/alerts/system", response_model=SystemAlertsResponse)
async def system_alerts(
    date: str,
    request: Request,
    lat: float = Query(..., ge=-89.9999, le=89.9999),
    lng: float = Query(..., ge=-180, le=180),
    timezone: Optional[str] = Query(None, description="Timezone IANA"),
    tz_offset_minutes: Optional[int] = Query(None, ge=-840, le=840),
    auth=Depends(get_auth),
):
    _parse_date_yyyy_mm_dd(date)
    dt = datetime.strptime(date, "%Y-%m-%d").replace(hour=12, minute=0, second=0)
    resolved_offset = _tz_offset_for(
        dt,
        timezone,
        tz_offset_minutes,
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
    )
    alerts: List[SystemAlert] = []

    mercury = _mercury_alert_for(date, lat, lng, resolved_offset)
    if mercury:
        alerts.append(mercury)

    severity_map = {"low": "baixo", "medium": "médio", "high": "alto"}
    alertas_ptbr = [
        {
            "id": alert.id,
            "severidade_ptbr": severity_map.get(alert.severity, alert.severity),
            "titulo_ptbr": alert.title,
            "mensagem_ptbr": alert.body,
            "technical": alert.technical,
        }
        for alert in alerts
    ]

    return SystemAlertsResponse(
        date=date,
        alerts=alerts,
        alertas_ptbr=alertas_ptbr,
        tipos_ptbr=severity_map,
    )


@app.get("/v1/alerts/retrogrades")
async def retrogrades_alerts(
    request: Request,
    date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    timezone: Optional[str] = Query(None, description="Timezone IANA"),
    tz_offset_minutes: Optional[int] = Query(None, ge=-840, le=840),
):
    if date:
        y, m, d = _parse_date_yyyy_mm_dd(date)
        local_dt = datetime(year=y, month=m, day=d, hour=12, minute=0, second=0)
    else:
        if timezone:
            try:
                tzinfo = ZoneInfo(timezone)
            except ZoneInfoNotFoundError:
                raise HTTPException(status_code=400, detail=f"Timezone inválido: {timezone}")
            local_dt = datetime.now(tzinfo).replace(hour=12, minute=0, second=0, microsecond=0)
        else:
            local_dt = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    resolved_offset = _tz_offset_for(
        local_dt,
        timezone,
        tz_offset_minutes,
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
    )
    utc_dt = local_dt - timedelta(minutes=resolved_offset)
    base_local = parse_local_datetime(datetime_local=local_dt)
    localized = localize_with_zoneinfo(base_local, timezone, tz_offset_minutes)
    utc_dt = to_utc(localized.datetime_local, localized.tz_offset_minutes)
    alerts = retrograde_alerts(utc_dt)
    retrogrades_ptbr = [
        {
            **alert,
            "planet_ptbr": planet_key_to_ptbr(str(alert.get("planet", "")).capitalize()),
            "status_ptbr": "Retrógrado" if alert.get("is_active") else "Direto",
        }
        for alert in alerts
    ]
    planetas_ptbr = [item["planet_ptbr"] for item in retrogrades_ptbr]
    return {
        "retrogrades": alerts,
        "retrogrades_ptbr": retrogrades_ptbr,
        "planetas_ptbr": planetas_ptbr,
        "timezone_resolvida": localized.timezone_resolved,
        "tz_offset_minutes_usado": localized.tz_offset_minutes,
        "fold_usado": localized.fold,
        "datetime_local_usado": localized.datetime_local.isoformat(),
        "datetime_utc_usado": utc_dt.isoformat(),
        "avisos": localized.warnings,
    }


@app.get("/v1/notifications/daily", response_model=NotificationsDailyResponse)
async def notifications_daily(
    request: Request,
    date: Optional[str] = None,
    lat: float = Query(..., ge=-89.9999, le=89.9999),
    lng: float = Query(..., ge=-180, le=180),
    timezone: Optional[str] = Query(None, description="Timezone IANA"),
    tz_offset_minutes: Optional[int] = Query(None, ge=-840, le=840),
    auth=Depends(get_auth),
):
    d = date or _now_yyyy_mm_dd()
    _parse_date_yyyy_mm_dd(d)
    dt = datetime.strptime(d, "%Y-%m-%d").replace(hour=12, minute=0, second=0)
    resolved_offset = _tz_offset_for(
        dt,
        timezone,
        tz_offset_minutes,
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
    )

    cache_key = f"notif:{auth['user_id']}:{d}:{lat}:{lng}:{timezone}:{resolved_offset}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    payload = _daily_notifications_payload(d, lat, lng, resolved_offset)
    cache.set(cache_key, payload.model_dump(), ttl_seconds=TTL_COSMIC_WEATHER_SECONDS)
    return payload
