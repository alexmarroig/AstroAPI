from __future__ import annotations
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import HTTPException

logger = logging.getLogger("astro-api")

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
    if datetime_local is not None:
        if isinstance(datetime_local, str):
            return datetime.fromisoformat(datetime_local.replace("Z", "+00:00")).replace(
                tzinfo=None
            )
        return datetime_local.replace(tzinfo=None)

    if year is None or month is None or day is None:
        raise ValueError("year, month, and day are required if datetime_local is not provided")

    return datetime(year, month, day, hour, minute, second)

def parse_date_yyyy_mm_dd(s: str) -> tuple[int, int, int]:
    """Analisa uma string no formato YYYY-MM-DD e retorna (ano, mês, dia)."""
    try:
        parsed = datetime.strptime(s, "%Y-%m-%d")
        return parsed.year, parsed.month, parsed.day
    except ValueError:
        # Tenta outros formatos comuns para robustez
        try:
            parsed = datetime.strptime(s, "%d/%m/%Y")
            return parsed.year, parsed.month, parsed.day
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato inválido de data. Use YYYY-MM-DD.")

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
        except Exception:
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

def resolve_birth_datetime_payload(data: Dict[str, Any]) -> tuple[Optional[datetime], Optional[bool], List[str]]:
    """Resolve a data e hora de nascimento a partir de diferentes formatos de entrada."""
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
            y, m, d = parse_date_yyyy_mm_dd(birth_date)
        except HTTPException:
            raise HTTPException(
                status_code=400,
                detail={"error": "DATA_INVALIDA", "message": "Data inválida. Use YYYY-MM-DD."},
            )
        if birth_time:
            h, minute, second = parse_time_hh_mm_ss(str(birth_time).strip())
            return datetime(year=y, month=m, day=d, hour=h, minute=minute, second=second), True, warnings
        warnings.append("Hora não informada; usando 12:00 como referência.")
        return datetime(year=y, month=m, day=d, hour=12, minute=0, second=0), False, warnings

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
    # Nota: Esta função consolida a lógica do _tz_offset_for do main.py
    if timezone_name:
        try:
            tzinfo = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            raise HTTPException(status_code=400, detail=f"Timezone inválido: {timezone_name}")

        offset_fold0 = date_time.replace(tzinfo=tzinfo, fold=0).utcoffset()
        offset_fold1 = date_time.replace(tzinfo=tzinfo, fold=1).utcoffset()

        if offset_fold0 is None and offset_fold1 is None:
            raise HTTPException(status_code=400, detail=f"Timezone sem offset disponível: {timezone_name}")

        if strict and offset_fold0 and offset_fold1 and offset_fold0 != offset_fold1:
            opts = sorted({int(offset_fold0.total_seconds() // 60), int(offset_fold1.total_seconds() // 60)})
            raise HTTPException(
                status_code=400,
                detail={
                    "detail": "Horário ambíguo na transição de horário de verão.",
                    "offset_options_minutes": opts,
                    "hint": "Envie tz_offset_minutes explicitamente ou ajuste o horário local.",
                },
            )

        # Se prefer_fold for fornecido, usa ele. Caso contrário, tenta o offset do fold 0
        offset = offset_fold0 if prefer_fold == 0 or prefer_fold is None else offset_fold1
        if offset is None: offset = offset_fold1 # Fallback

        return int(offset.total_seconds() // 60)

    if fallback_minutes is not None:
        return fallback_minutes

    return 0

def resolve_fold_for(
    date_time: Optional[datetime],
    timezone_name: Optional[str],
    tz_offset_minutes: Optional[int],
) -> Optional[int]:
    """Identifica qual 'fold' do horário de verão corresponde a um offset específico."""
    if date_time is None or not timezone_name or tz_offset_minutes is None:
        return None

    try:
        tzinfo = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return None

    target_offset = timedelta(minutes=tz_offset_minutes)
    offset_fold0 = date_time.replace(tzinfo=tzinfo, fold=0).utcoffset()
    offset_fold1 = date_time.replace(tzinfo=tzinfo, fold=1).utcoffset()

    if offset_fold0 == target_offset: return 0
    if offset_fold1 == target_offset: return 1
    return None

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
    """Localiza uma data ingênua usando ZoneInfo ou um offset de fallback."""
    warnings = []
    if timezone_name:
        try:
            tzinfo = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            raise HTTPException(status_code=400, detail=f"Timezone inválido: {timezone_name}")

        offset_fold0 = local_dt.replace(tzinfo=tzinfo, fold=0).utcoffset()
        offset_fold1 = local_dt.replace(tzinfo=tzinfo, fold=1).utcoffset()

        fold_used = 0
        offset = offset_fold0

        if offset_fold0 != offset_fold1:
            if fallback_minutes is not None:
                if fallback_minutes == int(offset_fold0.total_seconds() // 60):
                    fold_used = 0
                    offset = offset_fold0
                elif fallback_minutes == int(offset_fold1.total_seconds() // 60):
                    fold_used = 1
                    offset = offset_fold1
                else:
                    warnings.append("tz_offset_minutes não coincide com opções de DST; usando fold=0.")
            elif strict:
                raise HTTPException(status_code=400, detail="Horário ambíguo na transição de DST.")
            else:
                warnings.append("Horário ambíguo na transição de DST; usando fold=0.")

        if offset is None:
            raise HTTPException(status_code=400, detail="Timezone sem offset disponível.")

        return LocalizedDateTime(
            datetime_local=local_dt.replace(tzinfo=tzinfo, fold=fold_used),
            timezone_resolved=timezone_name,
            tz_offset_minutes=int(offset.total_seconds() // 60),
            fold=fold_used,
            warnings=warnings
        )

    return LocalizedDateTime(
        datetime_local=local_dt,
        timezone_resolved="UTC" if (fallback_minutes or 0) == 0 else "offset_manual",
        tz_offset_minutes=fallback_minutes or 0,
        fold=None,
        warnings=warnings
    )

def to_utc(local_dt: datetime, tz_offset_minutes: Optional[int] = None) -> datetime:
    """Converte uma data local para UTC."""
    if local_dt.tzinfo is not None:
        return local_dt.astimezone(timezone.utc).replace(tzinfo=None)
    if tz_offset_minutes is None:
        raise HTTPException(status_code=400, detail="Offset de timezone não informado.")
    return local_dt - timedelta(minutes=tz_offset_minutes)
