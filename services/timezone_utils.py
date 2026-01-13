from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
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
    )
