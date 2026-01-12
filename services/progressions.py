from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from astro.ephemeris import compute_chart


@dataclass(frozen=True)
class SecondaryProgressionResult:
    natal_datetime_local: str
    target_date: str
    progressed_datetime_local: str
    age_years: float
    tz_offset_minutes: int
    chart: dict


def calculate_secondary_progressions(
    natal_dt: datetime,
    target_date: datetime,
    lat: float,
    lng: float,
    tz_offset_minutes: int,
    house_system: str,
    zodiac_type: str,
    ayanamsa: str | None,
) -> SecondaryProgressionResult:
    age_days = (target_date - natal_dt).total_seconds() / 86400.0
    age_years = age_days / 365.25
    progressed_dt = natal_dt + timedelta(days=age_years)

    chart = compute_chart(
        year=progressed_dt.year,
        month=progressed_dt.month,
        day=progressed_dt.day,
        hour=progressed_dt.hour,
        minute=progressed_dt.minute,
        second=progressed_dt.second,
        lat=lat,
        lng=lng,
        tz_offset_minutes=tz_offset_minutes,
        house_system=house_system,
        zodiac_type=zodiac_type,
        ayanamsa=ayanamsa,
    )

    return SecondaryProgressionResult(
        natal_datetime_local=natal_dt.isoformat(),
        target_date=target_date.date().isoformat(),
        progressed_datetime_local=progressed_dt.isoformat(),
        age_years=round(age_years, 4),
        tz_offset_minutes=tz_offset_minutes,
        chart=chart,
    )
