from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException


@dataclass(frozen=True)
class LocalDatetimeResolution:
    datetime_local_used: datetime
    datetime_utc_used: datetime
    fold_used: Optional[int]
    warnings: List[str]


def _offset_candidates(
    date_time: datetime, tzinfo: ZoneInfo
) -> tuple[Optional[object], Optional[object]]:
    offset_fold0 = date_time.replace(tzinfo=tzinfo, fold=0).utcoffset()
    offset_fold1 = date_time.replace(tzinfo=tzinfo, fold=1).utcoffset()
    return offset_fold0, offset_fold1


def _matches_local_time(date_time: datetime, tzinfo: ZoneInfo, offset) -> bool:
    if offset is None:
        return False
    utc_candidate = date_time - offset
    local = tzinfo.fromutc(utc_candidate.replace(tzinfo=tzinfo))
    return local.replace(tzinfo=None) == date_time


def resolve_local_datetime(
    date_time: datetime, timezone: str, strict: bool = True
) -> LocalDatetimeResolution:
    if not timezone:
        raise HTTPException(status_code=400, detail="Timezone é obrigatório.")

    try:
        tzinfo = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(status_code=400, detail=f"Timezone inválido: {timezone}")

    offset_fold0, offset_fold1 = _offset_candidates(date_time, tzinfo)
    if offset_fold0 is None and offset_fold1 is None:
        raise HTTPException(status_code=400, detail=f"Timezone sem offset disponível: {timezone}")

    matches_fold0 = _matches_local_time(date_time, tzinfo, offset_fold0)
    matches_fold1 = _matches_local_time(date_time, tzinfo, offset_fold1)

    warnings: List[str] = []

    if matches_fold0 and matches_fold1 and offset_fold0 != offset_fold1:
        if strict:
            raise HTTPException(
                status_code=400,
                detail="Horário ambíguo na transição de horário de verão.",
            )
        fold_used = 0
        utc_dt = date_time - offset_fold0
        warnings.append(
            "Horário ambíguo na transição de horário de verão; fold=0 aplicado de forma determinística."
        )
        return LocalDatetimeResolution(date_time, utc_dt, fold_used, warnings)

    if not matches_fold0 and not matches_fold1:
        if strict:
            raise HTTPException(
                status_code=400,
                detail="Horário inexistente na transição de horário de verão.",
            )
        offset = offset_fold0 or offset_fold1
        utc_dt = date_time - offset
        local_adjusted = tzinfo.fromutc(utc_dt.replace(tzinfo=tzinfo)).replace(tzinfo=None)
        warnings.append(
            "Horário inexistente na transição de horário de verão; horário ajustado para o próximo válido."
        )
        return LocalDatetimeResolution(local_adjusted, utc_dt, 0, warnings)

    if matches_fold0:
        offset = offset_fold0
        fold_used = 0
    else:
        offset = offset_fold1
        fold_used = 1

    utc_dt = date_time - offset
    return LocalDatetimeResolution(date_time, utc_dt, fold_used, warnings)


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


def _roundtrip_valid(local_dt: datetime, tzinfo: ZoneInfo, fold: int) -> bool:
    candidate = local_dt.replace(tzinfo=tzinfo, fold=fold)
    utc_dt = candidate.astimezone(timezone.utc)
    roundtrip = utc_dt.astimezone(tzinfo)
    return roundtrip.replace(tzinfo=None) == local_dt


def _first_non_none(*values):
    """Return the first value that is not None.

    Important: timezone offsets can be zero (UTC) and zero-like values are falsy,
    therefore we must not rely on ``or`` when choosing fallback offsets.
    """

    for value in values:
        if value is not None:
            return value
    return None


def validate_local_datetime(
    local_datetime: datetime,
    timezone_name: str,
    strict: bool = False,
) -> LocalDatetimeValidation:
    try:
        tzinfo = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise HTTPException(status_code=400, detail=f"Timezone inválido: {timezone_name}")

    naive_local = local_datetime.replace(tzinfo=None)
    offset_fold0 = naive_local.replace(tzinfo=tzinfo, fold=0).utcoffset()
    offset_fold1 = naive_local.replace(tzinfo=tzinfo, fold=1).utcoffset()

    valid_fold0 = _roundtrip_valid(naive_local, tzinfo, fold=0)
    valid_fold1 = _roundtrip_valid(naive_local, tzinfo, fold=1)

    # Use explicit None checks because offset 0 minutes (UTC) is valid but falsy.
    ambiguous = (
        valid_fold0
        and valid_fold1
        and offset_fold0 is not None
        and offset_fold1 is not None
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
                    "hint": "Envie tz_offset_minutes explicitamente ou ajuste o horário local.",
                },
            )
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "Horário inexistente na transição de horário de verão.",
                "hint": "Ajuste o horário local ou envie outro horário válido.",
            },
        )

    warning: Optional[dict] = None
    adjustment_minutes = 0
    resolved_local = naive_local
    fold = 0

    if ambiguous:
        warning = {
            "code": "ambiguous_local_time",
            "message": "Horário ambíguo na transição de horário de verão.",
            "fold": 0,
        }
        fold = 0
        offset = _first_non_none(offset_fold0, offset_fold1)
    elif nonexistent:
        if (
            offset_fold0 is not None
            and offset_fold1 is not None
            and offset_fold1 > offset_fold0
        ):
            delta = offset_fold1 - offset_fold0
            adjustment_minutes = int(delta.total_seconds() // 60)
            resolved_local = naive_local + delta
            fold = 0
            offset = offset_fold1
        else:
            offset = _first_non_none(offset_fold0, offset_fold1)
        warning = {
            "code": "nonexistent_local_time",
            "message": "Horário inexistente na transição de horário de verão.",
            "adjustment_minutes": adjustment_minutes,
        }
    else:
        offset = _first_non_none(offset_fold0, offset_fold1)

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
