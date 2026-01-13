"""Timezone utility functions.

All functions are pure and avoid global state.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


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
    tz = ZoneInfo(tz_name)
    info: dict[str, object] = {"warnings": []}

    valid_folds = _valid_folds(dt_naive, tz)
    if not valid_folds:
        if strict:
            raise ValueError(
                f"Horário inexistente em {tz_name}: {dt_naive.isoformat()}"
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
        raise ValueError(
            f"Não foi possível ajustar horário inexistente em {tz_name}."
        )

    if len(valid_folds) == 2:
        offsets = {
            fold: dt_naive.replace(tzinfo=tz, fold=fold).utcoffset()
            for fold in valid_folds
        }
        if offsets[0] != offsets[1]:
            if strict:
                raise ValueError(
                    f"Horário ambíguo em {tz_name}: {dt_naive.isoformat()}"
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
        raise ValueError("Datetime não possui offset UTC.")
    return int(offset.total_seconds() // 60)
