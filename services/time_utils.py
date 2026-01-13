from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException

from core.timezone_utils import (
    TimezoneOffsetResult,
    TimezoneResolutionError,
    resolve_timezone_offset,
)


def parse_date_yyyy_mm_dd(date_str: str) -> tuple[int, int, int]:
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida. Use YYYY-MM-DD.")
    return parsed.year, parsed.month, parsed.day


def resolve_tz_offset(
    date_time: datetime,
    timezone: Optional[str],
    fallback_minutes: Optional[int],
    strict: bool = False,
    prefer_fold: Optional[int] = None,
) -> TimezoneOffsetResult:
    try:
        return resolve_timezone_offset(
            date_time=date_time,
            timezone=timezone,
            fallback_minutes=fallback_minutes,
            strict=strict,
            prefer_fold=prefer_fold,
        )
    except TimezoneResolutionError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc
