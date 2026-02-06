from __future__ import annotations

import warnings
from datetime import datetime

from fastapi import HTTPException

from core.timezone_utils import (
    LocalDatetimeResolution,
    LocalDatetimeValidation,
    TimezoneResolutionError,
    resolve_local_datetime as core_resolve_local_datetime,
    validate_local_datetime as core_validate_local_datetime,
)


def resolve_local_datetime(
    date_time: datetime, timezone_name: str, strict: bool = True
) -> LocalDatetimeResolution:
    warnings.warn(
        "services.timezone_utils.resolve_local_datetime está deprecated; use core.timezone_utils.resolve_local_datetime.",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        return core_resolve_local_datetime(date_time, timezone_name, strict=strict)
    except TimezoneResolutionError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc


def validate_local_datetime(
    local_datetime: datetime,
    timezone_name: str,
    strict: bool = False,
) -> LocalDatetimeValidation:
    warnings.warn(
        "services.timezone_utils.validate_local_datetime está deprecated; use core.timezone_utils.validate_local_datetime.",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        return core_validate_local_datetime(
            local_datetime,
            timezone_name,
            strict=strict,
        )
    except TimezoneResolutionError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc
