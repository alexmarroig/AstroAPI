from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


def parse_local_datetime(
    *,
    datetime_local: Optional[datetime] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> datetime:
    if datetime_local is not None:
        return datetime_local.replace(tzinfo=None)
    if year is None or month is None or day is None:
        raise HTTPException(status_code=400, detail="Data/hora local inválida.")
    return datetime(year, month, day, hour, minute, second)


@dataclass(frozen=True)
class LocalizedDateTime:
    datetime_local: datetime
    timezone_resolved: Optional[str]
    tz_offset_minutes: int
    fold: Optional[int]
    warnings: List[str]


def localize_with_zoneinfo(
    local_dt: datetime,
    timezone_name: Optional[str],
    fallback_minutes: Optional[int],
    strict: bool = False,
) -> LocalizedDateTime:
    warnings: List[str] = []
    fold_used: Optional[int] = None

    if timezone_name:
        try:
            tzinfo = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            raise HTTPException(status_code=400, detail=f"Timezone inválido: {timezone_name}")

        offset_fold0 = local_dt.replace(tzinfo=tzinfo, fold=0).utcoffset()
        offset_fold1 = local_dt.replace(tzinfo=tzinfo, fold=1).utcoffset()

        if offset_fold0 is None and offset_fold1 is None:
            raise HTTPException(status_code=400, detail=f"Timezone sem offset disponível: {timezone_name}")

        offset = offset_fold0 or offset_fold1

        if offset_fold0 and offset_fold1 and offset_fold0 != offset_fold1:
            options = {
                int(offset_fold0.total_seconds() // 60),
                int(offset_fold1.total_seconds() // 60),
            }
            if fallback_minutes is not None:
                if fallback_minutes in options:
                    fold_used = 0 if fallback_minutes == int(offset_fold0.total_seconds() // 60) else 1
                    offset = offset_fold0 if fold_used == 0 else offset_fold1
                else:
                    if strict:
                        raise HTTPException(
                            status_code=400,
                            detail={
                                "detail": "Horário ambíguo na transição de horário de verão.",
                                "offset_options_minutes": sorted(options),
                                "hint": "Envie tz_offset_minutes explicitamente ou ajuste o horário local.",
                            },
                        )
                    warnings.append(
                        "tz_offset_minutes não coincide com opções de DST; usando fold=0."
                    )
                    fold_used = 0
                    offset = offset_fold0
            elif strict:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "detail": "Horário ambíguo na transição de horário de verão.",
                        "offset_options_minutes": sorted(options),
                        "hint": "Envie tz_offset_minutes explicitamente ou ajuste o horário local.",
                    },
                )
            else:
                warnings.append("Horário ambíguo na transição de DST; usando fold=0.")
                fold_used = 0
                offset = offset_fold0

        if offset is None:
            raise HTTPException(status_code=400, detail=f"Timezone sem offset disponível: {timezone_name}")

        tz_offset_minutes = int(offset.total_seconds() // 60)
        if fallback_minutes is not None and fallback_minutes != tz_offset_minutes:
            warnings.append(
                "tz_offset_minutes fornecido difere do offset resolvido pelo timezone; usando timezone."
            )
        localized = local_dt.replace(tzinfo=tzinfo, fold=fold_used or 0)
        return LocalizedDateTime(
            datetime_local=localized,
            timezone_resolved=timezone_name,
            tz_offset_minutes=tz_offset_minutes,
            fold=fold_used,
            warnings=warnings,
        )

    if fallback_minutes is None:
        fallback_minutes = 0

    timezone_resolved = "UTC" if fallback_minutes == 0 else "offset_manual"
    return LocalizedDateTime(
        datetime_local=local_dt,
        timezone_resolved=timezone_resolved,
        tz_offset_minutes=fallback_minutes,
        fold=None,
        warnings=warnings,
    )


def to_utc(local_dt: datetime, tz_offset_minutes: Optional[int] = None) -> datetime:
    if local_dt.tzinfo is not None:
        return local_dt.astimezone(timezone.utc).replace(tzinfo=None)
    if tz_offset_minutes is None:
        raise HTTPException(status_code=400, detail="Offset de timezone não informado.")
    return local_dt - timedelta(minutes=tz_offset_minutes)


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
