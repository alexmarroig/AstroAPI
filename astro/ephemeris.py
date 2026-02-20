import calendar
from datetime import datetime, timedelta
from typing import Literal, Optional

import swisseph as swe

from astro.utils import angle_diff, to_julian_day, deg_to_sign

# garante funcionamento em cloud mesmo sem ephemeris externa
swe.set_ephe_path(".")

PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO
}

HOUSE_SYSTEMS = {
    'P': 'Placidus',
    'K': 'Koch',
    'O': 'Porphyrius',
    'R': 'Regiomontanus',
    'C': 'Campanus',
    'E': 'Equal',
    'W': 'Whole Sign'
}


AYANAMSA_MAP = {
    "lahiri": swe.SIDM_LAHIRI,
    "krishnamurti": swe.SIDM_KRISHNAMURTI,
    "ramey": swe.SIDM_RAMAN,
    "fagan_bradley": swe.SIDM_FAGAN_BRADLEY,
}


def compute_chart(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    lat: float,
    lng: float,
    tz_offset_minutes: int = 0,
    house_system: str = 'P',
    zodiac_type: Literal['tropical', 'sidereal'] = 'tropical',
    ayanamsa: Optional[str] = None,
) -> dict:
    local_dt = datetime(year, month, day, hour, minute, second)
    utc_dt = local_dt - timedelta(minutes=tz_offset_minutes)

    jd_ut = to_julian_day(utc_dt)
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED

    if zodiac_type == "sidereal":
        swe.set_sid_mode(AYANAMSA_MAP.get((ayanamsa or "lahiri").lower(), swe.SIDM_LAHIRI))
        flags |= swe.FLG_SIDEREAL

    # casas: fallback seguro
    warning = None
    house_system_code = house_system[0].upper() if house_system else "P"
    house_system_bytes = house_system_code.encode("ascii")

    try:
        cusps, ascmc = swe.houses_ex(jd_ut, lat, lng, house_system_bytes, flags)
    except Exception:
        # fallback para Placidus
        warning = "Sistema de casas ajustado automaticamente para Placidus por segurança."
        cusps, ascmc = swe.houses_ex(jd_ut, lat, lng, b'P', flags)
        house_system_code = "P"

    houses_data = {
        "system": HOUSE_SYSTEMS.get(house_system_code, house_system_code),
        "cusps": [round(c, 6) for c in cusps],  # cusps[0]..cusps[11] (12 valores)
        "asc": round(ascmc[0], 6),
        "mc": round(ascmc[1], 6)
    }

    planets_data = {}
    for name, planet_id in PLANETS.items():
        result, _ = swe.calc_ut(jd_ut, planet_id, flags)
        lon = result[0] % 360.0
        sign_info = deg_to_sign(lon)
        speed = result[3] if len(result) > 3 else None
        planets_data[name] = {
            "lon": round(lon, 6),
            "sign": sign_info["sign"],
            "deg_in_sign": round(sign_info["deg_in_sign"], 4),
            "speed": round(speed, 6) if speed is not None else None,
            "retrograde": bool(speed is not None and speed < 0),
        }

    payload = {
        "utc_datetime": utc_dt.isoformat(),
        "jd_ut": round(jd_ut, 8),
        "houses": houses_data,
        "planets": planets_data
    }
    if warning:
        payload["warning"] = warning

    return payload


def compute_transits(
    target_year: int,
    target_month: int,
    target_day: int,
    lat: float,
    lng: float,
    tz_offset_minutes: int = 0,
    zodiac_type: Literal['tropical', 'sidereal'] = 'tropical',
    ayanamsa: Optional[str] = None,
) -> dict:
    # 12:00 local como referência (estável)
    return compute_chart(
        year=target_year,
        month=target_month,
        day=target_day,
        hour=12,
        minute=0,
        second=0,
        lat=lat,
        lng=lng,
        tz_offset_minutes=tz_offset_minutes,
        house_system='P',
        zodiac_type=zodiac_type,
        ayanamsa=ayanamsa,
    )


def compute_moon_only(date_yyyy_mm_dd: str, tz_offset_minutes: int = 0) -> dict:
    """
    Retorna dados mínimos da Lua para Cosmic Weather:
    - longitude
    - signo (pt)
    - ângulo de fase Sol–Lua (0..360)

    Usa 12:00 local como referência para estabilidade diária.
    """
    try:
        year, month, day = map(int, date_yyyy_mm_dd.split("-"))
    except Exception:
        raise ValueError("Data inválida. Use YYYY-MM-DD.")

    # 12:00 local → UTC
    local_dt = datetime(year, month, day, 12, 0, 0)
    utc_dt = local_dt - timedelta(minutes=tz_offset_minutes)

    jd_ut = to_julian_day(utc_dt)

    moon_res, _ = swe.calc_ut(jd_ut, swe.MOON)
    moon_lon = moon_res[0] % 360.0

    sun_res, _ = swe.calc_ut(jd_ut, swe.SUN)
    sun_lon = sun_res[0] % 360.0

    phase_angle = (moon_lon - sun_lon) % 360.0

    sign_info = deg_to_sign(moon_lon)

    return {
        "utc_datetime": utc_dt.isoformat(),
        "moon_lon": round(moon_lon, 6),
        "moon_sign": sign_info["sign"],
        "deg_in_sign": round(sign_info["deg_in_sign"], 4),
        "phase_angle_deg": round(phase_angle, 4)
    }


def _planet_longitude(utc_dt: datetime, planet_id: int) -> float:
    jd_ut = to_julian_day(utc_dt)
    result, _ = swe.calc_ut(jd_ut, planet_id)
    return result[0] % 360.0


def find_longitude_match(
    *,
    planet_id: int,
    target_lon: float,
    start_local: datetime,
    end_local: datetime,
    tz_offset_minutes: int = 0,
    tolerance_deg: float = 0.1,
    step_minutes: int = 60,
    refine_steps: int = 12,
) -> dict:
    if end_local <= start_local:
        raise ValueError("end_local must be after start_local")

    start_utc = start_local - timedelta(minutes=tz_offset_minutes)
    end_utc = end_local - timedelta(minutes=tz_offset_minutes)

    if end_utc <= start_utc:
        raise ValueError("end_local must be after start_local")

    step_seconds = max(60, int(step_minutes * 60))
    best_utc = start_utc
    best_delta = 360.0
    current = start_utc
    while current <= end_utc:
        lon = _planet_longitude(current, planet_id)
        delta = angle_diff(lon, target_lon)
        if delta < best_delta:
            best_delta = delta
            best_utc = current
        if best_delta <= tolerance_deg:
            break
        current += timedelta(seconds=step_seconds)

    center = best_utc
    window_seconds = step_seconds
    for _ in range(refine_steps):
        if window_seconds <= 1:
            break
        half_window = max(1, window_seconds // 2)
        candidates = [
            max(start_utc, center - timedelta(seconds=half_window)),
            center,
            min(end_utc, center + timedelta(seconds=half_window)),
        ]
        for candidate in candidates:
            lon = _planet_longitude(candidate, planet_id)
            delta = angle_diff(lon, target_lon)
            if delta < best_delta:
                best_delta = delta
                center = candidate
        window_seconds = half_window

    center = center.replace(microsecond=0)
    best_lon = _planet_longitude(center, planet_id)
    local_dt = (center + timedelta(minutes=tz_offset_minutes)).replace(microsecond=0)
    return {
        "local_datetime": local_dt.isoformat(),
        "utc_datetime": center.isoformat(),
        "planet_lon": round(best_lon, 6),
        "delta_deg": round(best_delta, 6),
    }
def _sun_longitude_at(dt: datetime) -> float:
    jd_ut = to_julian_day(dt)
    result, _ = swe.calc_ut(jd_ut, swe.SUN)
    return result[0] % 360.0


def sun_longitude_at(utc_dt: datetime) -> float:
    return _sun_longitude_at(utc_dt)


def _angle_delta(lon: float, target: float) -> float:
    return ((lon - target + 180.0) % 360.0) - 180.0


def _target_year_datetime(natal_dt: datetime, target_year: int) -> datetime:
    day = min(natal_dt.day, calendar.monthrange(target_year, natal_dt.month)[1])
    return natal_dt.replace(year=target_year, day=day)


def _solar_return_v1(
    natal_lon: float,
    approx_dt: datetime,
    window_days: int = 2,
    step_hours: int = 1,
) -> datetime:
    window_start = approx_dt - timedelta(days=window_days)
    best_dt = window_start
    best_delta = 360.0
    total_hours = int((window_days * 2 * 24) / step_hours)
    for step in range(total_hours + 1):
        candidate = window_start + timedelta(hours=step * step_hours)
        delta = abs(_angle_delta(_sun_longitude_at(candidate), natal_lon))
        if delta < best_delta:
            best_delta = delta
            best_dt = candidate
    return best_dt


def _solar_return_v2(
    natal_lon: float,
    approx_dt: datetime,
    window_days: int = 3,
    step_hours: int = 6,
    max_iter: int = 60,
    tolerance_degrees: float = 1e-6,
) -> Optional[datetime]:
    window_start = approx_dt - timedelta(days=window_days)
    window_end = approx_dt + timedelta(days=window_days)
    step = timedelta(hours=step_hours)

    prev_dt = window_start
    prev_delta = _angle_delta(sun_longitude_at(prev_dt), natal_lon)
    if prev_delta == 0:
        return prev_dt

    current = window_start + step
    bracket = None
    while current <= window_end:
        current_delta = _angle_delta(sun_longitude_at(current), natal_lon)
        if current_delta == 0:
            return current
        if prev_delta * current_delta < 0:
            bracket = (prev_dt, current)
            break
        prev_dt, prev_delta = current, current_delta
        current += step

    if bracket is None:
        return None

    left_dt, right_dt = bracket
    left_delta = _angle_delta(sun_longitude_at(left_dt), natal_lon)
    right_delta = _angle_delta(sun_longitude_at(right_dt), natal_lon)

    for _ in range(max_iter):
        midpoint = left_dt + (right_dt - left_dt) / 2
        mid_delta = _angle_delta(sun_longitude_at(midpoint), natal_lon)
        if abs(mid_delta) < 1e-6 or (right_dt - left_dt).total_seconds() <= 1:
            return midpoint
        if left_delta * mid_delta < 0:
            right_dt = midpoint
            right_delta = mid_delta
        else:
            left_dt = midpoint
            left_delta = mid_delta

    return left_dt + (right_dt - left_dt) / 2


def solar_return_datetime(
    natal_dt: datetime,
    target_year: int,
    tz_offset_minutes: int = 0,
    engine: Literal["v1", "v2"] = "v1",
    window_days: Optional[int] = None,
    step_hours: Optional[int] = None,
    max_iter: Optional[int] = None,
    tolerance_degrees: Optional[float] = None,
) -> datetime:
    natal_utc = natal_dt - timedelta(minutes=tz_offset_minutes)
    natal_lon = _sun_longitude_at(natal_utc)
    approx_local = _target_year_datetime(natal_dt, target_year)
    approx_utc = approx_local - timedelta(minutes=tz_offset_minutes)

    if engine == "v2":
        result = _solar_return_v2(
            natal_lon,
            approx_utc,
            window_days=window_days or 3,
            step_hours=step_hours or 6,
            max_iter=max_iter or 60,
            tolerance_degrees=tolerance_degrees or 1e-6,
        )
        if result is not None:
            return result

    return _solar_return_v1(
        natal_lon,
        approx_utc,
        window_days=window_days or 2,
        step_hours=step_hours or 1,
    )
