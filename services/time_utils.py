from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException


def parse_date_yyyy_mm_dd(date_str: str) -> tuple[int, int, int]:
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida. Use YYYY-MM-DD.")
    return parsed.year, parsed.month, parsed.day


def parse_local_datetime(date_str: str, time_str: Optional[str] = None) -> datetime:
    try:
        date_part = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato inválido de data. Use YYYY-MM-DD.")

    time_value = time_str or "12:00:00"
    parsed_time: Optional[time] = None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            parsed_time = datetime.strptime(time_value, fmt).time()
            break
        except ValueError:
            continue
    if parsed_time is None:
        raise HTTPException(status_code=400, detail="Formato inválido de hora. Use HH:MM:SS.")

    return datetime.combine(date_part, parsed_time)


def localize_with_zoneinfo(local_dt: datetime, timezone_name: str, strict: bool = False) -> datetime:
    if not timezone_name:
        raise HTTPException(status_code=400, detail="Timezone inválido: ")
    try:
        tzinfo = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise HTTPException(status_code=400, detail=f"Timezone inválido: {timezone_name}")

    offset_fold0 = local_dt.replace(tzinfo=tzinfo, fold=0).utcoffset()
    offset_fold1 = local_dt.replace(tzinfo=tzinfo, fold=1).utcoffset()

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

    fold = 0 if offset_fold0 is not None else 1
    return local_dt.replace(tzinfo=tzinfo, fold=fold)


def utc_offset_minutes(
    local_dt: datetime,
    timezone_name: Optional[str],
    fallback_minutes: Optional[int],
    strict: bool = False,
) -> int:
    if timezone_name:
        localized = localize_with_zoneinfo(local_dt, timezone_name, strict=strict)
        offset = localized.utcoffset()
        if offset is None:
            raise HTTPException(status_code=400, detail=f"Timezone sem offset disponível: {timezone_name}")
        return int(offset.total_seconds() // 60)

    if fallback_minutes is not None:
        return fallback_minutes

    return 0


def to_utc(
    local_dt: datetime,
    timezone_name: Optional[str],
    fallback_minutes: Optional[int],
    strict: bool = False,
) -> datetime:
    if timezone_name:
        localized = localize_with_zoneinfo(local_dt, timezone_name, strict=strict)
        return localized.astimezone(timezone.utc).replace(tzinfo=None)

    offset = fallback_minutes or 0
    return local_dt - timedelta(minutes=offset)


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
