from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException


DEFAULT_TIME = (12, 0, 0)
DEFAULT_TIME_STR = "12:00:00"


def parse_local_datetime(
    date_str: str, time_str: Optional[str]
) -> tuple[datetime, list[str], bool]:
    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato inválido de data. Use YYYY-MM-DD.")

    warnings: list[str] = []
    time_missing = False

    if time_str:
        try:
            hour, minute, second = map(int, time_str.split(":"))
        except Exception:
            raise HTTPException(status_code=422, detail="Hora natal inválida. Use HH:MM:SS.")
    else:
        hour, minute, second = DEFAULT_TIME
        time_missing = True
        warnings.append(f"hora ausente; assumido {DEFAULT_TIME_STR}")

    return datetime(
        year=parsed_date.year,
        month=parsed_date.month,
        day=parsed_date.day,
        hour=hour,
        minute=minute,
        second=second,
    ), warnings, time_missing
