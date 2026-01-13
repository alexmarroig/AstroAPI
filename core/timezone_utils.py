from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class TimezoneOffsetResult:
    offset_minutes: int
    warnings: list[str]
    fold_used: Optional[int]
    is_ambiguous: bool
    is_nonexistent: bool


class TimezoneResolutionError(ValueError):
    def __init__(self, message: str, detail: Optional[dict | str] = None) -> None:
        super().__init__(message)
        self.detail = detail if detail is not None else message


def resolve_timezone_offset(
    date_time: datetime,
    timezone: Optional[str],
    fallback_minutes: Optional[int],
    strict: bool = False,
    prefer_fold: Optional[int] = None,
) -> TimezoneOffsetResult:
    if prefer_fold not in (None, 0, 1):
        raise TimezoneResolutionError("prefer_fold inválido. Use 0, 1 ou None.")

    warnings: list[str] = []
    fold_used: Optional[int] = None
    is_ambiguous = False
    is_nonexistent = False

    if timezone:
        try:
            tzinfo = ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise TimezoneResolutionError(f"Timezone inválido: {timezone}") from exc

        if date_time.tzinfo is not None:
            localized = date_time.astimezone(tzinfo)
            offset = localized.utcoffset()
            if offset is None:
                raise TimezoneResolutionError(f"Timezone sem offset disponível: {timezone}")
            return TimezoneOffsetResult(
                offset_minutes=int(offset.total_seconds() // 60),
                warnings=warnings,
                fold_used=localized.fold,
                is_ambiguous=False,
                is_nonexistent=False,
            )

        dt_fold0 = date_time.replace(tzinfo=tzinfo, fold=0)
        dt_fold1 = date_time.replace(tzinfo=tzinfo, fold=1)

        offset_fold0 = dt_fold0.utcoffset()
        offset_fold1 = dt_fold1.utcoffset()

        if offset_fold0 is None and offset_fold1 is None:
            raise TimezoneResolutionError(f"Timezone sem offset disponível: {timezone}")

        roundtrip_fold0 = dt_fold0.astimezone(tzinfo).replace(tzinfo=None)
        roundtrip_fold1 = dt_fold1.astimezone(tzinfo).replace(tzinfo=None)

        is_ambiguous = (
            offset_fold0 is not None
            and offset_fold1 is not None
            and offset_fold0 != offset_fold1
            and roundtrip_fold0 == date_time
            and roundtrip_fold1 == date_time
        )
        is_nonexistent = roundtrip_fold0 != date_time and roundtrip_fold1 != date_time

        if is_ambiguous or is_nonexistent:
            fold_used = prefer_fold if prefer_fold in (0, 1) else 0

        if is_ambiguous:
            if strict:
                opts = sorted(
                    {
                        int(offset_fold0.total_seconds() // 60),
                        int(offset_fold1.total_seconds() // 60),
                    }
                )
                raise TimezoneResolutionError(
                    "Horário ambíguo na transição de horário de verão.",
                    detail={
                        "detail": "Horário ambíguo na transição de horário de verão.",
                        "offset_options_minutes": opts,
                        "hint": "Envie tz_offset_minutes explicitamente ou ajuste o horário local.",
                    },
                )
            warnings.append(
                "Horário ambíguo na transição de horário de verão. "
                f"Usando fold={fold_used}."
            )

        if is_nonexistent:
            if strict:
                raise TimezoneResolutionError(
                    "Horário inexistente na transição de horário de verão.",
                    detail={
                        "detail": "Horário inexistente na transição de horário de verão.",
                        "hint": "Ajuste o horário local ou envie tz_offset_minutes explicitamente.",
                    },
                )
            warnings.append(
                "Horário inexistente na transição de horário de verão. "
                f"Usando fold={fold_used}."
            )

        offset = None
        if fold_used == 1 and offset_fold1 is not None:
            offset = offset_fold1
        elif fold_used == 0 and offset_fold0 is not None:
            offset = offset_fold0
        else:
            offset = offset_fold0 or offset_fold1

        if offset is None:
            raise TimezoneResolutionError(f"Timezone sem offset disponível: {timezone}")

        return TimezoneOffsetResult(
            offset_minutes=int(offset.total_seconds() // 60),
            warnings=warnings,
            fold_used=fold_used,
            is_ambiguous=is_ambiguous,
            is_nonexistent=is_nonexistent,
        )

    if fallback_minutes is not None:
        return TimezoneOffsetResult(
            offset_minutes=fallback_minutes,
            warnings=warnings,
            fold_used=None,
            is_ambiguous=False,
            is_nonexistent=False,
        )

    return TimezoneOffsetResult(
        offset_minutes=0,
        warnings=warnings,
        fold_used=None,
        is_ambiguous=False,
        is_nonexistent=False,
    )
