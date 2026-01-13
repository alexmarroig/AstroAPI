from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException


@dataclass(frozen=True)
class LocalDateTimeValidation:
    utc_datetime: datetime
    tz_offset_minutes: int
    flags: dict[str, Any]
    warnings: list[dict[str, Any]]


def _parse_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida. Use YYYY-MM-DD.")


def _parse_time(time_str: str) -> tuple[int, int, int]:
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            parsed = datetime.strptime(time_str, fmt)
            return parsed.hour, parsed.minute, parsed.second
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail="Hora inválida. Use HH:MM ou HH:MM:SS.")


def _roundtrip_valid(local_dt: datetime, tzinfo: ZoneInfo, fold: int) -> bool:
    candidate = local_dt.replace(tzinfo=tzinfo, fold=fold)
    utc_dt = candidate.astimezone(timezone.utc)
    roundtrip = utc_dt.astimezone(tzinfo)
    return roundtrip.replace(tzinfo=None) == local_dt


def validate_local_datetime(
    *,
    date_str: str,
    time_str: str,
    timezone_name: str,
    strict: bool = False,
    prefer_fold: int = 0,
) -> LocalDateTimeValidation:
    local_date = _parse_date(date_str)
    hour, minute, second = _parse_time(time_str)
    local_dt = local_date.replace(hour=hour, minute=minute, second=second)

class LocalDatetimeValidation:
    input_datetime: datetime
    resolved_datetime: datetime
    timezone: str
    tz_offset_minutes: int
    utc_datetime: datetime
    fold: int
    warning: Optional[dict]
    adjustment_minutes: int = 0


def validate_local_datetime(
    local_datetime: datetime,
    timezone_name: str,
    strict: bool = False,
) -> LocalDatetimeValidation:
    try:
        tzinfo = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise HTTPException(status_code=400, detail=f"Timezone inválido: {timezone_name}")

    offset_fold0 = local_dt.replace(tzinfo=tzinfo, fold=0).utcoffset()
    offset_fold1 = local_dt.replace(tzinfo=tzinfo, fold=1).utcoffset()
    valid_fold0 = _roundtrip_valid(local_dt, tzinfo, fold=0)
    valid_fold1 = _roundtrip_valid(local_dt, tzinfo, fold=1)

    ambiguous = (
        valid_fold0
        and valid_fold1
        and offset_fold0
        and offset_fold1
        and offset_fold0 != offset_fold1
    )
    nonexistent = not valid_fold0 and not valid_fold1

    if strict and (ambiguous or nonexistent):
        if ambiguous:
            options = sorted(
                {int(offset_fold0.total_seconds() // 60), int(offset_fold1.total_seconds() // 60)}
            )
    naive_local = local_datetime.replace(tzinfo=None)

    fold0 = naive_local.replace(tzinfo=tzinfo, fold=0)
    fold1 = naive_local.replace(tzinfo=tzinfo, fold=1)

    offset_fold0 = fold0.utcoffset()
    offset_fold1 = fold1.utcoffset()

    if offset_fold0 is None and offset_fold1 is None:
        raise HTTPException(status_code=400, detail=f"Timezone sem offset disponível: {timezone_name}")

    warning: Optional[dict] = None
    adjustment_minutes = 0
    resolved_local = naive_local
    fold = 0

    if offset_fold0 and offset_fold1 and offset_fold0 != offset_fold1:
        if strict:
            if offset_fold1 > offset_fold0:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "detail": "Horário inexistente na transição de horário de verão.",
                        "code": "nonexistent_local_time",
                        "hint": "Ajuste o horário local ou envie um horário válido.",
                    },
                )
            raise HTTPException(
                status_code=400,
                detail={
                    "detail": "Horário ambíguo na transição de horário de verão.",
                    "offset_options_minutes": options,
                    "hint": "Informe prefer_fold (0 ou 1) para escolher o offset correto.",
                    "flags": {"ambiguous": True, "nonexistent": False},
                },
            )
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "Horário inexistente na transição de horário de verão.",
                "hint": "Ajuste a hora local para um momento válido.",
                "flags": {"ambiguous": False, "nonexistent": True},
            },
        )

    warnings: list[dict[str, Any]] = []
    used_fold = 1 if prefer_fold == 1 else 0

    if ambiguous:
        options = sorted(
            {int(offset_fold0.total_seconds() // 60), int(offset_fold1.total_seconds() // 60)}
        )
        warnings.append(
            {
                "code": "ambiguous_time",
                "message": "Horário ambíguo na transição de horário de verão.",
                "offset_options_minutes": options,
                "used_fold": used_fold,
            }
        )

    if nonexistent:
        warnings.append(
            {
                "code": "nonexistent_time",
                "message": "Horário inexistente na transição de horário de verão.",
                "hint": "Ajuste a hora local para um momento válido.",
                "used_fold": used_fold,
            }
        )

    if ambiguous:
        selected_offset = offset_fold1 if used_fold == 1 else offset_fold0
    else:
        selected_offset = offset_fold0 or offset_fold1

    if selected_offset is None:
        raise HTTPException(status_code=400, detail=f"Timezone sem offset disponível: {timezone_name}")

    utc_dt = local_dt.replace(tzinfo=tzinfo, fold=used_fold).astimezone(timezone.utc)
    tz_offset_minutes = int(selected_offset.total_seconds() // 60)

    return LocalDateTimeValidation(
        utc_datetime=utc_dt,
        tz_offset_minutes=tz_offset_minutes,
        flags={"ambiguous": ambiguous, "nonexistent": nonexistent, "used_fold": used_fold},
        warnings=warnings,
                    "code": "ambiguous_local_time",
                    "hint": "Envie tz_offset_minutes explicitamente ou ajuste o horário local.",
                },
            )

        if offset_fold1 > offset_fold0:
            delta = offset_fold1 - offset_fold0
            adjustment_minutes = int(delta.total_seconds() // 60)
            resolved_local = naive_local + delta
            fold = 1
            warning = {
                "code": "nonexistent_local_time",
                "message": (
                    "Horário inexistente na transição de horário de verão. "
                    "Ajustado para o próximo horário válido."
                ),
                "adjustment_minutes": adjustment_minutes,
            }
            offset = offset_fold1
        else:
            fold = 1
            warning = {
                "code": "ambiguous_local_time",
                "message": (
                    "Horário ambíguo na transição de horário de verão. "
                    "Usando o segundo horário válido (fold=1)."
                ),
                "fold": fold,
            }
            offset = offset_fold1
    else:
        offset = offset_fold0 or offset_fold1

    if offset is None:
        raise HTTPException(status_code=400, detail=f"Timezone sem offset disponível: {timezone_name}")

    tz_offset_minutes = int(offset.total_seconds() // 60)
    aware_local = resolved_local.replace(tzinfo=tzinfo, fold=fold)
    utc_dt = aware_local.astimezone(timezone.utc)

    return LocalDatetimeValidation(
        input_datetime=naive_local,
        resolved_datetime=resolved_local,
        timezone=timezone_name,
        tz_offset_minutes=tz_offset_minutes,
        utc_datetime=utc_dt,
        fold=fold,
        warning=warning,
        adjustment_minutes=adjustment_minutes,
    )
