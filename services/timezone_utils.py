from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException


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
