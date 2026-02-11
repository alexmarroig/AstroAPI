from __future__ import annotations
import logging
import re
import warnings
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, NamedTuple
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import HTTPException

from core.timezone_utils import (
    TimezoneResolutionError,
    localize_with_zoneinfo as core_localize_with_zoneinfo,
    parse_date_yyyy_mm_dd as core_parse_date_yyyy_mm_dd,
    parse_local_datetime_components as core_parse_local_datetime_components,
    parse_time_hh_mm_ss as core_parse_time_hh_mm_ss,
    resolve_fold_for as core_resolve_fold_for,
    resolve_timezone_offset,
    to_utc as core_to_utc,
)

logger = logging.getLogger("astro-api")


@dataclass
class NormalizedBirthData:
    datetime_local: Optional[datetime]
    birth_time_precise: Optional[bool]
    tz_offset_minutes: Optional[int]
    timezone: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    warnings: List[str]

class LocalizedDateTime(NamedTuple):
    datetime_local: datetime
    timezone_resolved: str
    tz_offset_minutes: int
    fold: Optional[int]
    warnings: List[str]

def parse_local_datetime(
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    datetime_local: Optional[datetime] = None,
) -> datetime:
    """Cria um objeto datetime a partir de componentes ou de um objeto datetime/string (naive)."""
    warnings.warn(
        "services.time_utils.parse_local_datetime está deprecated; use core.timezone_utils.parse_local_datetime_components.",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        return core_parse_local_datetime_components(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=second,
            datetime_local=datetime_local,
        )
    except TimezoneResolutionError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc

def parse_date_yyyy_mm_dd(s: str) -> tuple[int, int, int]:
    """Analisa uma string no formato YYYY-MM-DD e retorna (ano, mês, dia)."""
    warnings.warn(
        "services.time_utils.parse_date_yyyy_mm_dd está deprecated; use core.timezone_utils.parse_date_yyyy_mm_dd.",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        return core_parse_date_yyyy_mm_dd(s)
    except TimezoneResolutionError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc

def parse_local_datetime_ptbr(
    date_str: str, time_str: Optional[str]
) -> tuple[datetime, list[str], bool]:
    """
    Analisa data e hora local com suporte a formatos brasileiros extensos.
    Exemplo: '7 de novembro de 1995'
    """
    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        parsed_date = None

    if parsed_date is None:
        try:
            parsed_date = datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
            parsed_date = None

    if parsed_date is None:
        match = re.match(r"^\s*(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})\s*$", date_str.strip(), re.I)
        if match:
            day = int(match.group(1))
            month_name = match.group(2).lower()
            year = int(match.group(3))
            months = {
                "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
                "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
                "outubro": 10, "novembro": 11, "dezembro": 12,
            }
            month = months.get(month_name)
            if month:
                try:
                    parsed_date = datetime(year=year, month=month, day=day)
                except ValueError:
                    parsed_date = None

    if parsed_date is None:
        raise HTTPException(
            status_code=400,
            detail="Formato inválido de data. Use YYYY-MM-DD, DD/MM/AAAA ou 'D de mês de AAAA'.",
        )

    warnings: list[str] = []
    time_missing = False

    if time_str:
        try:
            h, m, s = parse_time_hh_mm_ss(time_str)
        except HTTPException:
            raise HTTPException(status_code=422, detail="Hora natal inválida. Use HH:MM:SS.")
    else:
        h, m, s = (12, 0, 0)
        time_missing = True
        warnings.append("hora ausente; assumido 12:00:00")

    return datetime(
        year=parsed_date.year, month=parsed_date.month, day=parsed_date.day,
        hour=h, minute=m, second=s
    ), warnings, time_missing

def parse_time_hh_mm_ss(s: str) -> tuple[int, int, int]:
    """Analisa uma string no formato HH:MM ou HH:MM:SS e retorna (hora, minuto, segundo)."""
    warnings.warn(
        "services.time_utils.parse_time_hh_mm_ss está deprecated; use core.timezone_utils.parse_time_hh_mm_ss.",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        return core_parse_time_hh_mm_ss(s)
    except TimezoneResolutionError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "HORA_INVALIDA", "message": str(exc)},
        ) from exc

def resolve_birth_datetime_payload(data: Dict[str, Any]) -> tuple[Optional[datetime], Optional[bool], List[str]]:
    """Resolve a data/hora natal a partir de formatos ISO, birth_* e componentes year/natal_year."""
    normalized = normalize_birth_payload(data)
    return normalized.datetime_local, normalized.birth_time_precise, normalized.warnings


def normalize_birth_payload(data: Dict[str, Any]) -> NormalizedBirthData:
    """Normaliza payload de nascimento aceitando camelCase/snake_case e componentes numéricos."""
    warnings: List[str] = []
    birth_datetime = data.get("birth_datetime") or data.get("birthDateTime") or data.get("birthDatetime")
    birth_date = data.get("birth_date") or data.get("birthDate")
    birth_time = data.get("birth_time") or data.get("birthTime")
    tz_offset_minutes = data.get("tz_offset_minutes", data.get("tzOffsetMinutes"))
    timezone_name = data.get("timezone")
    lat_raw = data.get("lat", data.get("latitude"))
    lng_raw = data.get("lng", data.get("longitude"))

    lat = float(lat_raw) if lat_raw is not None else None
    lng = float(lng_raw) if lng_raw is not None else None

    if timezone_name:
        try:
            ZoneInfo(str(timezone_name))
        except ZoneInfoNotFoundError:
            raise HTTPException(status_code=422, detail="Invalid timezone. Use an IANA timezone like America/Sao_Paulo.")

    tz_offset_int = None
    if tz_offset_minutes is not None:
        try:
            tz_offset_int = int(tz_offset_minutes)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail={"error": "TZ_OFFSET_INVALIDO", "message": "tz_offset_minutes inválido."})

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
            return NormalizedBirthData(parsed, False, tz_offset_int, timezone_name, lat, lng, warnings)
        return NormalizedBirthData(parsed, True, tz_offset_int, timezone_name, lat, lng, warnings)

    if birth_date:
        birth_date = str(birth_date).strip()
        try:
            y, m, d = parse_date_yyyy_mm_dd(birth_date)
        except HTTPException:
            raise HTTPException(
                status_code=400,
                detail={"error": "DATA_INVALIDA", "message": "Data inválida. Use YYYY-MM-DD."},
            )
        if birth_time:
            h, minute, second = parse_time_hh_mm_ss(str(birth_time).strip())
            return NormalizedBirthData(
                datetime(year=y, month=m, day=d, hour=h, minute=minute, second=second),
                True,
                tz_offset_int,
                timezone_name,
                lat,
                lng,
                warnings,
            )
        warnings.append("Hora não informada; usando 12:00 como referência.")
        return NormalizedBirthData(
            datetime(year=y, month=m, day=d, hour=12, minute=0, second=0),
            False,
            tz_offset_int,
            timezone_name,
            lat,
            lng,
            warnings,
        )

    # Fallback para componentes já normalizados no front/proxy ou enviados diretamente.
    year = data.get("natal_year", data.get("year"))
    month = data.get("natal_month", data.get("month"))
    day = data.get("natal_day", data.get("day"))
    hour = data.get("natal_hour", data.get("hour"))
    minute = data.get("natal_minute", data.get("minute", 0))
    second = data.get("natal_second", data.get("second", 0))

    has_date_components = year is not None and month is not None and day is not None
    has_time_components = hour is not None

    if has_date_components and has_time_components:
        try:
            return NormalizedBirthData(
                datetime(
                    year=int(year),
                    month=int(month),
                    day=int(day),
                    hour=int(hour),
                    minute=int(minute or 0),
                    second=int(second or 0),
                ),
                True,
                tz_offset_int,
                timezone_name,
                lat,
                lng,
                warnings,
            )
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail={"error": "DATA_INVALIDA", "message": "Componentes de data/hora inválidos."},
            )

    return NormalizedBirthData(None, None, tz_offset_int, timezone_name, lat, lng, warnings)
    # Fallback para componentes já normalizados no front/proxy ou enviados diretamente.
    year = data.get("natal_year", data.get("year"))
    month = data.get("natal_month", data.get("month"))
    day = data.get("natal_day", data.get("day"))
    hour = data.get("natal_hour", data.get("hour"))
    minute = data.get("natal_minute", data.get("minute", 0))
    second = data.get("natal_second", data.get("second", 0))

    has_date_components = year is not None and month is not None and day is not None
    has_time_components = hour is not None

    if has_date_components and has_time_components:
        try:
            return (
                datetime(
                    year=int(year),
                    month=int(month),
                    day=int(day),
                    hour=int(hour),
                    minute=int(minute or 0),
                    second=int(second or 0),
                ),
                True,
                warnings,
            )
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail={"error": "DATA_INVALIDA", "message": "Componentes de data/hora inválidos."},
            )

    return None, None, warnings

def get_tz_offset_minutes(
    date_time: datetime,
    timezone_name: Optional[str],
    fallback_minutes: Optional[int],
    strict: bool = False,
    request_id: Optional[str] = None,
    path: Optional[str] = None,
    prefer_fold: Optional[int] = None,
) -> int:
    """Resolve o offset de timezone (em minutos) para uma determinada data/hora."""
    try:
        result = resolve_timezone_offset(
            date_time,
            timezone_name,
            fallback_minutes,
            strict=strict,
            prefer_fold=prefer_fold,
        )
    except TimezoneResolutionError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc
    return result.offset_minutes


def resolve_fold_for(
    date_time: Optional[datetime],
    timezone_name: Optional[str],
    tz_offset_minutes: Optional[int],
) -> Optional[int]:
    """Identifica qual 'fold' do horário de verão corresponde a um offset específico."""
    warnings.warn(
        "services.time_utils.resolve_fold_for está deprecated; use core.timezone_utils.resolve_fold_for.",
        DeprecationWarning,
        stacklevel=2,
    )
    return core_resolve_fold_for(date_time, timezone_name, tz_offset_minutes)

def build_time_metadata(
    timezone_name: Optional[str],
    tz_offset_minutes: Optional[int],
    local_dt: Optional[datetime],
    avisos: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Constrói o payload de metadados técnicos relacionados ao tempo."""
    utc_dt = (
        local_dt - timedelta(minutes=tz_offset_minutes)
        if local_dt is not None and tz_offset_minutes is not None
        else None
    )
    return {
        "timezone_resolvida": timezone_name,
        "timezone_usada": timezone_name,
        "tz_offset_minutes_usado": tz_offset_minutes,
        "tz_offset_minutes": tz_offset_minutes,
        "fold_usado": resolve_fold_for(local_dt, timezone_name, tz_offset_minutes),
        "datetime_local_usado": local_dt.isoformat() if local_dt else None,
        "datetime_utc_usado": utc_dt.isoformat() if utc_dt else None,
        "avisos": avisos or [],
    }

def localize_with_zoneinfo(
    local_dt: datetime,
    timezone_name: Optional[str],
    fallback_minutes: Optional[int],
    strict: bool = False,
) -> LocalizedDateTime:
    """Localiza uma data ingênua usando funções canônicas de `core.timezone_utils`."""
    warnings.warn(
        "services.time_utils.localize_with_zoneinfo está deprecated; use core.timezone_utils.localize_with_zoneinfo.",
        DeprecationWarning,
        stacklevel=2,
    )

    if timezone_name:
        try:
            localized_dt, info = core_localize_with_zoneinfo(
                local_dt,
                timezone_name,
                strict=strict,
                prefer_fold=0,
            )
            tz_offset = int(localized_dt.utcoffset().total_seconds() // 60)
        except TimezoneResolutionError as exc:
            raise HTTPException(status_code=400, detail=exc.detail) from exc
        fold_used = info.get("fold_used")
        fold = int(fold_used) if fold_used in (0, 1) else None
        return LocalizedDateTime(
            datetime_local=localized_dt,
            timezone_resolved=timezone_name,
            tz_offset_minutes=tz_offset,
            fold=fold,
            warnings=list(info.get("warnings", [])),
        )

    return LocalizedDateTime(
        datetime_local=local_dt,
        timezone_resolved="UTC" if (fallback_minutes or 0) == 0 else "offset_manual",
        tz_offset_minutes=fallback_minutes or 0,
        fold=None,
        warnings=[],
    )


def to_utc(local_dt: datetime, tz_offset_minutes: Optional[int] = None) -> datetime:
    """Converte uma data local para UTC."""
    warnings.warn(
        "services.time_utils.to_utc está deprecated; use core.timezone_utils.to_utc.",
        DeprecationWarning,
        stacklevel=2,
    )
    if local_dt.tzinfo is not None:
        return core_to_utc(local_dt).replace(tzinfo=None)
    if tz_offset_minutes is None:
        raise HTTPException(status_code=400, detail="Offset de timezone não informado.")
    return local_dt - timedelta(minutes=tz_offset_minutes)
