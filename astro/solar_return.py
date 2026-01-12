from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Literal, Optional

import swisseph as swe

from astro.aspects import ASPECTS
from astro.ephemeris import AYANAMSA_MAP, compute_chart
from astro.utils import angle_diff, deg_to_sign, to_julian_day


ZodiacType = Literal["tropical", "sidereal"]


@dataclass(frozen=True)
class SolarReturnConfig:
    zodiac_type: ZodiacType = "tropical"
    ayanamsa: Optional[str] = None
    allow_sidereal: bool = False
    house_system: str = "P"
    allow_custom_house_system: bool = False


def _resolve_zodiac(config: SolarReturnConfig) -> tuple[ZodiacType, int]:
    zodiac_type = config.zodiac_type if config.allow_sidereal else "tropical"
    if zodiac_type == "sidereal":
        swe.set_sid_mode(
            AYANAMSA_MAP.get((config.ayanamsa or "lahiri").lower(), swe.SIDM_LAHIRI)
        )
        return zodiac_type, swe.FLG_SIDEREAL
    return zodiac_type, 0


def _sun_longitude(jd_ut: float, flags: int) -> float:
    result, _ = swe.calc_ut(jd_ut, swe.SUN, flags)
    return result[0] % 360.0


def compute_natal_sun_longitude(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    tz_offset_minutes: int = 0,
    zodiac_type: ZodiacType = "tropical",
    ayanamsa: Optional[str] = None,
    allow_sidereal: bool = False,
) -> dict:
    local_dt = datetime(year, month, day, hour, minute, second)
    utc_dt = local_dt - timedelta(minutes=tz_offset_minutes)
    jd_ut = to_julian_day(utc_dt)

    config = SolarReturnConfig(
        zodiac_type=zodiac_type,
        ayanamsa=ayanamsa,
        allow_sidereal=allow_sidereal,
    )
    _, flags = _resolve_zodiac(config)
    lon = _sun_longitude(jd_ut, flags)
    sign_info = deg_to_sign(lon)

    return {
        "utc_datetime": utc_dt.isoformat(),
        "jd_ut": round(jd_ut, 8),
        "sun_lon": round(lon, 6),
        "sign": sign_info["sign"],
        "deg_in_sign": round(sign_info["deg_in_sign"], 4),
    }


def find_solar_return_instant(
    natal_sun_lon: float,
    target_year: int,
    birth_month: int,
    birth_day: int,
    tz_offset_minutes: int = 0,
    zodiac_type: ZodiacType = "tropical",
    ayanamsa: Optional[str] = None,
    allow_sidereal: bool = False,
    window_days: int = 3,
    step_hours: int = 6,
    max_iter: int = 60,
    tolerance_degrees: float = 1e-6,
) -> dict:
    config = SolarReturnConfig(
        zodiac_type=zodiac_type,
        ayanamsa=ayanamsa,
        allow_sidereal=allow_sidereal,
    )
    _, flags = _resolve_zodiac(config)

    base_local_dt = datetime(target_year, birth_month, birth_day, 12, 0, 0)
    base_utc_dt = base_local_dt - timedelta(minutes=tz_offset_minutes)

    start_dt = base_utc_dt - timedelta(days=window_days)
    end_dt = base_utc_dt + timedelta(days=window_days)

    start_jd = to_julian_day(start_dt)
    end_jd = to_julian_day(end_dt)

    def delta(jd_ut: float) -> float:
        lon = _sun_longitude(jd_ut, flags)
        return (lon - natal_sun_lon + 540.0) % 360.0 - 180.0

    bracket_start = start_jd
    bracket_end = start_jd
    step_days = step_hours / 24.0
    prev_jd = start_jd
    prev_delta = delta(prev_jd)

    found = False
    current_jd = start_jd + step_days
    while current_jd <= end_jd + 1e-9:
        current_delta = delta(current_jd)
        if prev_delta == 0:
            bracket_start = prev_jd
            bracket_end = prev_jd
            found = True
            break
        if (prev_delta < 0 <= current_delta) or (prev_delta > 0 >= current_delta):
            bracket_start = prev_jd
            bracket_end = current_jd
            found = True
            break
        prev_jd = current_jd
        prev_delta = current_delta
        current_jd += step_days

    if not found:
        raise ValueError("Não foi possível localizar o retorno solar na janela informada.")

    if bracket_start == bracket_end:
        jd_ut = bracket_start
    else:
        low = bracket_start
        high = bracket_end
        for _ in range(max_iter):
            mid = (low + high) / 2.0
            mid_delta = delta(mid)
            if abs(mid_delta) <= tolerance_degrees:
                low = high = mid
                break
            if (delta(low) < 0 <= mid_delta) or (delta(low) > 0 >= mid_delta):
                high = mid
            else:
                low = mid
        jd_ut = (low + high) / 2.0

    utc_dt = datetime(2000, 1, 1) + timedelta(days=jd_ut - 2451544.5)
    lon = _sun_longitude(jd_ut, flags)
    sign_info = deg_to_sign(lon)

    return {
        "utc_datetime": utc_dt.isoformat(),
        "jd_ut": round(jd_ut, 8),
        "sun_lon": round(lon, 6),
        "sign": sign_info["sign"],
        "deg_in_sign": round(sign_info["deg_in_sign"], 4),
        "window_days": window_days,
    }


def compute_solar_return_chart(
    solar_return_utc: datetime,
    lat: float,
    lng: float,
    tz_offset_minutes: int = 0,
    house_system: str = "P",
    zodiac_type: ZodiacType = "tropical",
    ayanamsa: Optional[str] = None,
    allow_custom_house_system: bool = False,
    allow_sidereal: bool = False,
) -> dict:
    config = SolarReturnConfig(
        zodiac_type=zodiac_type,
        ayanamsa=ayanamsa,
        allow_sidereal=allow_sidereal,
        house_system=house_system,
        allow_custom_house_system=allow_custom_house_system,
    )
    zodiac_type, _ = _resolve_zodiac(config)
    house_system = house_system if allow_custom_house_system else "P"

    local_dt = solar_return_utc + timedelta(minutes=tz_offset_minutes)
    return compute_chart(
        year=local_dt.year,
        month=local_dt.month,
        day=local_dt.day,
        hour=local_dt.hour,
        minute=local_dt.minute,
        second=local_dt.second,
        lat=lat,
        lng=lng,
        tz_offset_minutes=tz_offset_minutes,
        house_system=house_system,
        zodiac_type=zodiac_type,
        ayanamsa=ayanamsa,
    )


def compute_aspects(
    transit_planets: Dict[str, dict],
    natal_planets: Dict[str, dict],
    aspects: Optional[Dict[str, dict]] = None,
) -> List[dict]:
    aspects_found: List[dict] = []
    aspects = aspects or ASPECTS

    for t_name, t_data in transit_planets.items():
        t_lon = t_data["lon"]

        for n_name, n_data in natal_planets.items():
            n_lon = n_data["lon"]
            separation = angle_diff(t_lon, n_lon)

            for aspect_name, aspect_info in aspects.items():
                target_angle = aspect_info["angle"]
                max_orb = aspect_info["orb"]
                orb = abs(separation - target_angle)

                if orb <= max_orb:
                    aspects_found.append({
                        "transit_planet": t_name,
                        "natal_planet": n_name,
                        "aspect": aspect_name,
                        "exact_angle": target_angle,
                        "actual_angle": round(separation, 4),
                        "orb": round(orb, 4),
                        "influence": aspect_info["influence"],
                    })

    aspects_found.sort(key=lambda x: x["orb"])
    return aspects_found


def build_interpretation_ptbr(
    solar_return_chart: dict,
    aspects: List[dict],
    builder: Optional[Callable[[dict, List[dict]], dict]] = None,
) -> dict:
    if builder:
        return builder(solar_return_chart, aspects)

    return {
        "resumo": "Interpretação automática não configurada.",
        "destaques": [],
        "aspectos": aspects,
    }
