from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import swisseph as swe

from astro.utils import deg_to_sign, sign_to_pt, to_julian_day


@dataclass(frozen=True)
class LunationResult:
    date: str
    timezone: str | None
    tz_offset_minutes: int
    phase_angle_deg: float
    phase: str
    phase_pt: str
    is_waxing: bool
    moon_sign: str
    moon_sign_pt: str
    sun_sign: str
    sun_sign_pt: str


PHASES = [
    ("new", "Lua Nova", 0.0, 22.5),
    ("waxing_crescent", "Lua Crescente", 22.5, 67.5),
    ("first_quarter", "Quarto Crescente", 67.5, 112.5),
    ("waxing_gibbous", "Gibosa Crescente", 112.5, 157.5),
    ("full", "Lua Cheia", 157.5, 202.5),
    ("waning_gibbous", "Gibosa Minguante", 202.5, 247.5),
    ("last_quarter", "Quarto Minguante", 247.5, 292.5),
    ("waning_crescent", "Lua Minguante", 292.5, 337.5),
    ("new", "Lua Nova", 337.5, 360.0),
]


def _phase_for_angle(angle_deg: float) -> tuple[str, str]:
    for key, label, start, end in PHASES:
        if start <= angle_deg < end:
            return key, label
    return "new", "Lua Nova"


def calculate_lunation(date: datetime, tz_offset_minutes: int, timezone: str | None) -> LunationResult:
    local_dt = date.replace(hour=12, minute=0, second=0, microsecond=0)
    utc_dt = local_dt - timedelta(minutes=tz_offset_minutes)
    jd_ut = to_julian_day(utc_dt)

    moon_res, _ = swe.calc_ut(jd_ut, swe.MOON)
    sun_res, _ = swe.calc_ut(jd_ut, swe.SUN)
    moon_lon = moon_res[0] % 360.0
    sun_lon = sun_res[0] % 360.0
    phase_angle = (moon_lon - sun_lon) % 360.0

    phase_key, phase_label = _phase_for_angle(phase_angle)
    is_waxing = phase_angle <= 180.0

    moon_sign = deg_to_sign(moon_lon)["sign"]
    sun_sign = deg_to_sign(sun_lon)["sign"]

    return LunationResult(
        date=local_dt.date().isoformat(),
        timezone=timezone,
        tz_offset_minutes=tz_offset_minutes,
        phase_angle_deg=round(phase_angle, 4),
        phase=phase_key,
        phase_pt=phase_label,
        is_waxing=is_waxing,
        moon_sign=moon_sign,
        moon_sign_pt=sign_to_pt(moon_sign),
        sun_sign=sun_sign,
        sun_sign_pt=sign_to_pt(sun_sign),
    )
