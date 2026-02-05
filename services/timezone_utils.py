from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException

from core.timezone_utils import (
    TimezoneResolutionError,
    localize_with_zoneinfo as core_localize_with_zoneinfo,
)


@dataclass(frozen=True)
class LocalDatetimeResolution:
    datetime_local_used: datetime
    datetime_utc_used: datetime
    fold_used: Optional[int]
    warnings: List[str]


@dataclass(frozen=True)
class LocalDatetimeValidation:
    input_datetime: datetime
    resolved_datetime: datetime
    timezone: str
    tz_offset_minutes: int
    utc_datetime: datetime
    fold: int
    warning: Optional[dict]
    adjustment_minutes: int = 0


def resolve_local_datetime(
    date_time: datetime, timezone_name: str, strict: bool = True
) -> LocalDatetimeResolution:
    warnings.warn(
        "services.timezone_utils.resolve_local_datetime está deprecated; use core.timezone_utils.localize_with_zoneinfo.",
        DeprecationWarning,
        stacklevel=2,
    )
    if not timezone_name:
        raise HTTPException(status_code=400, detail="Timezone é obrigatório.")
    try:
        localized, info = core_localize_with_zoneinfo(
            date_time,
            timezone_name,
            strict=strict,
            prefer_fold=0,
        )
    except TimezoneResolutionError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc

    return LocalDatetimeResolution(
        datetime_local_used=localized.replace(tzinfo=None),
        datetime_utc_used=localized.astimezone(timezone.utc).replace(tzinfo=None),
        fold_used=info.get("fold_used") if info.get("fold_used") in (0, 1) else None,
        warnings=list(info.get("warnings", [])),
    )


def validate_local_datetime(
    local_datetime: datetime,
    timezone_name: str,
    strict: bool = False,
) -> LocalDatetimeValidation:
    warnings.warn(
        "services.timezone_utils.validate_local_datetime está deprecated; use core.timezone_utils.localize_with_zoneinfo.",
        DeprecationWarning,
        stacklevel=2,
    )
    naive_local = local_datetime.replace(tzinfo=None)

    classification: Optional[str] = None
    if strict:
        try:
            core_localize_with_zoneinfo(
                naive_local,
                timezone_name,
                strict=True,
                prefer_fold=0,
            )
        except TimezoneResolutionError as exc:
            raise HTTPException(status_code=400, detail=exc.detail) from exc
    else:
        try:
            core_localize_with_zoneinfo(
                naive_local,
                timezone_name,
                strict=True,
                prefer_fold=0,
            )
        except TimezoneResolutionError as exc:
            msg = str(exc)
            if "ambíguo" in msg:
                classification = "ambiguous"
            elif "inexistente" in msg:
                classification = "nonexistent"

    try:
        localized, info = core_localize_with_zoneinfo(
            naive_local,
            timezone_name,
            strict=False,
            prefer_fold=0,
        )
    except TimezoneResolutionError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc

    resolved_local = localized.replace(tzinfo=None)
    utc_dt = localized.astimezone(timezone.utc)
    fold_used = info.get("fold_used") if info.get("fold_used") in (0, 1) else 0
    tz_offset_minutes = int(localized.utcoffset().total_seconds() // 60)
    adjustment_minutes = int(info.get("adjusted_minutes", 0) or 0)
    warning = None

    if classification == "nonexistent" or adjustment_minutes:
        warning = {
            "code": "nonexistent_local_time",
            "message": "Horário inexistente na transição de horário de verão.",
            "adjustment_minutes": adjustment_minutes,
        }
    elif classification == "ambiguous":
        warning = {
            "code": "ambiguous_local_time",
            "message": "Horário ambíguo na transição de horário de verão.",
            "fold": fold_used,
        }

    return LocalDatetimeValidation(
        input_datetime=naive_local,
        resolved_datetime=resolved_local,
        timezone=timezone_name,
        tz_offset_minutes=tz_offset_minutes,
        utc_datetime=utc_dt,
        fold=fold_used,
        warning=warning,
        adjustment_minutes=adjustment_minutes,
    )
