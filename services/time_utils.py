from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException


def parse_date_yyyy_mm_dd(date_str: str) -> tuple[int, int, int]:
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida. Use YYYY-MM-DD.")
    return parsed.year, parsed.month, parsed.day


def parse_time_hh_mm_ss(time_str: str) -> tuple[int, int, int]:
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            parsed = datetime.strptime(time_str, fmt)
            return parsed.hour, parsed.minute, parsed.second
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail="Hora inválida. Use HH:MM ou HH:MM:SS.")


def analyze_local_datetime(date_time: datetime, timezone_name: str) -> dict:
    try:
        tzinfo = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise HTTPException(status_code=400, detail=f"Timezone inválido: {timezone_name}")

    aware_fold0 = date_time.replace(tzinfo=tzinfo, fold=0)
    aware_fold1 = date_time.replace(tzinfo=tzinfo, fold=1)
    offset_fold0 = aware_fold0.utcoffset()
    offset_fold1 = aware_fold1.utcoffset()

    def _roundtrip_local(aware_dt: datetime) -> datetime:
        return aware_dt.astimezone(timezone.utc).astimezone(tzinfo).replace(tzinfo=None)

    valid_fold0 = _roundtrip_local(aware_fold0) == date_time
    valid_fold1 = _roundtrip_local(aware_fold1) == date_time

    is_nonexistent = not valid_fold0 and not valid_fold1
    is_ambiguous = valid_fold0 and valid_fold1 and offset_fold0 != offset_fold1

    return {
        "tzinfo": tzinfo,
        "offset_fold0": offset_fold0,
        "offset_fold1": offset_fold1,
        "is_ambiguous": is_ambiguous,
        "is_nonexistent": is_nonexistent,
    }


def resolve_tz_offset(
    date_time: datetime,
    timezone: Optional[str],
    fallback_minutes: Optional[int],
    strict: bool = False,
) -> int:
    if timezone:
        try:
            tzinfo = ZoneInfo(timezone)
        except ZoneInfoNotFoundError:
            raise HTTPException(status_code=400, detail=f"Timezone inválido: {timezone}")

        offset_fold0 = date_time.replace(tzinfo=tzinfo, fold=0).utcoffset()
        offset_fold1 = date_time.replace(tzinfo=tzinfo, fold=1).utcoffset()

        offset = offset_fold0 or offset_fold1
        if offset is None:
            raise HTTPException(status_code=400, detail=f"Timezone sem offset disponível: {timezone}")

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

        return int(offset.total_seconds() // 60)

    if fallback_minutes is not None:
        return fallback_minutes

    return 0
