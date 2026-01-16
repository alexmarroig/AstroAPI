from __future__ import annotations

from datetime import datetime
import re
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
        parsed_date = None
    if parsed_date is None:
        try:
            parsed_date = datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
            parsed_date = None
    if parsed_date is None:
        match = re.match(r"^\s*(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})\s*$", date_str.strip(), re.I)
        if match:
            day = int(match.group(1))
            month_name = match.group(2).lower()
            year = int(match.group(3))
            months = {
                "janeiro": 1,
                "fevereiro": 2,
                "março": 3,
                "marco": 3,
                "abril": 4,
                "maio": 5,
                "junho": 6,
                "julho": 7,
                "agosto": 8,
                "setembro": 9,
                "outubro": 10,
                "novembro": 11,
                "dezembro": 12,
            }
            month = months.get(month_name)
            if month:
                try:
                    parsed_date = datetime(year=year, month=month, day=day)
                except ValueError:
                    parsed_date = None
    if parsed_date is None:
        raise HTTPException(
            status_code=400,
            detail="Formato inválido de data. Use YYYY-MM-DD, DD/MM/AAAA ou 'D de mês de AAAA'.",
        )

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
