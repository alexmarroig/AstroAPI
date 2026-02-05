"""Timezone utility functions.

All functions are pure and avoid global state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def parse_local_datetime(date_str: str, time_str: str | None) -> tuple[datetime, list[str]]:
    """Parse date/time strings into a naive datetime.

    Uses 12:00:00 when time_str is absent and returns a warning.
    """
    warnings: list[str] = []
    parsed_date = datetime.fromisoformat(date_str).date()
    if time_str:
        parsed_time = time.fromisoformat(time_str)
    else:
        parsed_time = time(12, 0, 0)
        warnings.append("Hora ausente: usando 12:00:00 como padrão.")
    return datetime.combine(parsed_date, parsed_time), warnings


def _valid_folds(dt_naive: datetime, tz: ZoneInfo) -> list[int]:
    valid_folds: list[int] = []
    for fold in (0, 1):
        candidate = dt_naive.replace(tzinfo=tz, fold=fold)
        back = candidate.astimezone(timezone.utc).astimezone(tz)
        if back.replace(tzinfo=None) == dt_naive:
            valid_folds.append(fold)
    return valid_folds


def localize_with_zoneinfo(
    dt_naive: datetime,
    tz_name: str,
    strict: bool = True,
    prefer_fold: int = 0,
) -> tuple[datetime, dict[str, object]]:
    """Attach ZoneInfo to a naive datetime with DST handling.

    Returns the aware datetime and metadata (warnings, fold_used).
    """
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise TimezoneResolutionError(f"Timezone inválido: {tz_name}") from exc
    info: dict[str, object] = {"warnings": []}

    valid_folds = _valid_folds(dt_naive, tz)
    if not valid_folds:
        if strict:
            raise TimezoneResolutionError(
                f"Horário inexistente em {tz_name}: {dt_naive.isoformat()}",
                detail={
                    "detail": "Horário inexistente na transição de horário de verão.",
                    "hint": "Ajuste o horário local ou envie tz_offset_minutes explicitamente.",
                },
            )
        for minutes in range(1, 181):
            adjusted = dt_naive + timedelta(minutes=minutes)
            adjusted_folds = _valid_folds(adjusted, tz)
            if adjusted_folds:
                chosen_fold = (
                    prefer_fold if prefer_fold in adjusted_folds else adjusted_folds[0]
                )
                info["warnings"].append(
                    "Horário inexistente: ajustado para o próximo instante válido."
                )
                info["adjusted_minutes"] = minutes
                info["fold_used"] = chosen_fold
                return adjusted.replace(tzinfo=tz, fold=chosen_fold), info
        raise TimezoneResolutionError(
            f"Não foi possível ajustar horário inexistente em {tz_name}."
        )

    if len(valid_folds) == 2:
        offsets = {
            fold: dt_naive.replace(tzinfo=tz, fold=fold).utcoffset()
            for fold in valid_folds
        }
        if offsets[0] != offsets[1]:
            if strict:
                opts = sorted(
                    {
                        int(offsets[0].total_seconds() // 60),
                        int(offsets[1].total_seconds() // 60),
                    }
                )
                raise TimezoneResolutionError(
                    f"Horário ambíguo em {tz_name}: {dt_naive.isoformat()}",
                    detail={
                        "detail": "Horário ambíguo na transição de horário de verão.",
                        "offset_options_minutes": opts,
                        "hint": "Envie tz_offset_minutes explicitamente ou ajuste o horário local.",
                    },
                )
            chosen_fold = prefer_fold if prefer_fold in valid_folds else valid_folds[0]
            info["fold_used"] = chosen_fold
            return dt_naive.replace(tzinfo=tz, fold=chosen_fold), info

    chosen_fold = valid_folds[0]
    info["fold_used"] = chosen_fold
    return dt_naive.replace(tzinfo=tz, fold=chosen_fold), info


def to_utc(dt_aware: datetime) -> datetime:
    """Convert aware datetime to UTC."""
    return dt_aware.astimezone(timezone.utc)


def utc_offset_minutes(dt_aware: datetime) -> int:
    """Return UTC offset in minutes for an aware datetime."""
    offset = dt_aware.utcoffset()
    if offset is None:
        raise TimezoneResolutionError("Datetime não possui offset UTC.")
    return int(offset.total_seconds() // 60)


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
