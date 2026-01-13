from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
