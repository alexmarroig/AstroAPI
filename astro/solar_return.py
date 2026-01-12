from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional, Literal, Dict, Any

import swisseph as swe
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from astro.ephemeris import compute_chart, AYANAMSA_MAP
from astro.aspects import compute_transit_aspects
from astro.utils import deg_to_sign, to_julian_day


def _normalize_angle(angle: float) -> float:
    return angle % 360.0


def _signed_angle_diff(a: float, b: float) -> float:
    return ((a - b + 180.0) % 360.0) - 180.0


def _jd_to_datetime_utc(jd_ut: float) -> datetime:
    year, month, day, hour = swe.revjul(jd_ut)
    hour_int = int(hour)
    minute = int((hour - hour_int) * 60)
    second = int(round((((hour - hour_int) * 60) - minute) * 60))
    if second == 60:
        second = 59
    return datetime(year, month, day, hour_int, minute, second)


def _safe_date(year: int, month: int, day: int) -> datetime:
    try:
        return datetime(year, month, day)
    except ValueError:
        if month == 2 and day == 29:
            return datetime(year, 2, 28)
        raise


def _resolve_tz_offset_minutes(local_dt: datetime, timezone: Optional[str]) -> int:
    if not timezone:
        return 0
    try:
        tzinfo = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Timezone inválido: {timezone}") from exc

    offset = local_dt.replace(tzinfo=tzinfo).utcoffset()
    if offset is None:
        return 0
    return int(offset.total_seconds() // 60)


def compute_natal_sun_longitude(jd_ut: float, zodiac_type: Literal["tropical", "sidereal"],
                                ayanamsa: Optional[str]) -> float:
    if zodiac_type == "sidereal":
        swe.set_sid_mode(AYANAMSA_MAP.get((ayanamsa or "lahiri").lower(), swe.SIDM_LAHIRI))
    result, _ = swe.calc_ut(jd_ut, swe.SUN)
    return _normalize_angle(result[0])


def find_solar_return_instant(
    natal_sun_lon: float,
    target_year: int,
    natal_month: int,
    natal_day: int,
    timezone: Optional[str],
    zodiac_type: Literal["tropical", "sidereal"],
    ayanamsa: Optional[str],
    engine: Literal["v1", "v2"] = "v1",
) -> Dict[str, Any]:
    base_local = _safe_date(target_year, natal_month, natal_day)
    base_local = base_local.replace(hour=12, minute=0, second=0)
    tz_offset = _resolve_tz_offset_minutes(base_local, timezone)
    base_utc = base_local - timedelta(minutes=tz_offset)
    center_jd = to_julian_day(base_utc)

    def f(jd: float) -> float:
        sun_lon = compute_natal_sun_longitude(jd, zodiac_type, ayanamsa)
        return _signed_angle_diff(sun_lon, natal_sun_lon)

    step = 1.0 / 24.0
    window_days = 3
    start_jd = center_jd - window_days
    end_jd = center_jd + window_days

    if engine == "v1":
        best_jd = center_jd
        best_diff = 360.0
        current = start_jd
        while current <= end_jd:
            diff = abs(f(current))
            if diff < best_diff:
                best_diff = diff
                best_jd = current
            current += step
        return {
            "jd_ut": best_jd,
            "diff_deg": abs(f(best_jd)),
            "bracket_found": False,
        }

    prev_jd = start_jd
    prev_f = f(prev_jd)
    bracket = None
    current = prev_jd + step
    while current <= end_jd:
        curr_f = f(current)
        if prev_f == 0:
            bracket = (prev_jd, prev_jd)
            break
        if prev_f * curr_f < 0:
            bracket = (prev_jd, current)
            break
        prev_jd, prev_f = current, curr_f
        current += step

    if bracket is None:
        best_jd = center_jd
        best_diff = 360.0
        current = start_jd
        while current <= end_jd:
            diff = abs(f(current))
            if diff < best_diff:
                best_diff = diff
                best_jd = current
            current += step
        return {
            "jd_ut": best_jd,
            "diff_deg": abs(f(best_jd)),
            "bracket_found": False,
        }

    left, right = bracket
    if left == right:
        return {
            "jd_ut": left,
            "diff_deg": 0.0,
            "bracket_found": True,
        }

    tolerance_deg = 1e-5
    tolerance_days = 0.1 / 86400
    for _ in range(80):
        mid = (left + right) / 2.0
        mid_f = f(mid)
        if abs(mid_f) <= tolerance_deg or (right - left) < tolerance_days:
            return {
                "jd_ut": mid,
                "diff_deg": abs(mid_f),
                "bracket_found": True,
            }
        left_f = f(left)
        if left_f * mid_f <= 0:
            right = mid
        else:
            left = mid

    final_f = f(mid)
    return {
        "jd_ut": mid,
        "diff_deg": abs(final_f),
        "bracket_found": True,
    }


def compute_solar_return_chart(
    jd_ut: float,
    lat: float,
    lng: float,
    timezone: Optional[str],
    house_system: str,
    zodiac_type: Literal["tropical", "sidereal"],
    ayanamsa: Optional[str],
) -> Dict[str, Any]:
    utc_dt = _jd_to_datetime_utc(jd_ut)
    if timezone:
        try:
            tzinfo = ZoneInfo(timezone)
            local_dt = utc_dt.replace(tzinfo=dt_timezone.utc).astimezone(tzinfo)
        except Exception:
            local_dt = utc_dt
    else:
        local_dt = utc_dt

    tz_offset_minutes = _resolve_tz_offset_minutes(local_dt.replace(tzinfo=None), timezone)

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
    solar_planets: Dict[str, dict],
    natal_planets: Dict[str, dict],
) -> list[dict]:
    return compute_transit_aspects(transit_planets=solar_planets, natal_planets=natal_planets)


def build_interpretation_ptbr(metadados: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "cabecalho": (
            f"Sua Revolução Solar de {metadados['ano_alvo']} vai de {metadados['instante_local']} "
            "até a véspera do próximo retorno."
        ),
        "temas_do_ano": [
            {"tema": "Propósito", "acao": "Defina uma meta prática para o ano."},
            {"tema": "Equilíbrio", "acao": "Revise rotinas e priorize descanso."},
            {"tema": "Crescimento", "acao": "Invista em um aprendizado contínuo."},
        ],
        "perguntas_reflexao": [
            "O que precisa amadurecer neste ciclo?",
            "Onde vale simplificar para ganhar clareza?",
            "Qual compromisso você quer honrar até o próximo retorno?",
        ],
    }


@dataclass
class SolarReturnInputs:
    natal_date: datetime
    natal_lat: float
    natal_lng: float
    natal_timezone: Optional[str]
    target_year: int
    target_lat: float
    target_lng: float
    target_timezone: Optional[str]
    house_system: str
    zodiac_type: Literal["tropical", "sidereal"]
    ayanamsa: Optional[str]
    engine: Literal["v1", "v2"]
    tz_offset_minutes: Optional[int]
    natal_time_missing: bool


def compute_solar_return_payload(inputs: SolarReturnInputs) -> Dict[str, Any]:
    tz_offset_natal = _resolve_tz_offset_minutes(inputs.natal_date, inputs.natal_timezone)
    natal_utc = inputs.natal_date - timedelta(minutes=tz_offset_natal)
    natal_jd = to_julian_day(natal_utc)
    natal_sun_lon = compute_natal_sun_longitude(natal_jd, inputs.zodiac_type, inputs.ayanamsa)
    natal_sign = deg_to_sign(natal_sun_lon)

    result = find_solar_return_instant(
        natal_sun_lon=natal_sun_lon,
        target_year=inputs.target_year,
        natal_month=inputs.natal_date.month,
        natal_day=inputs.natal_date.day,
        timezone=inputs.target_timezone,
        zodiac_type=inputs.zodiac_type,
        ayanamsa=inputs.ayanamsa,
        engine=inputs.engine,
    )

    solar_chart = compute_solar_return_chart(
        jd_ut=result["jd_ut"],
        lat=inputs.target_lat,
        lng=inputs.target_lng,
        timezone=inputs.target_timezone,
        house_system=inputs.house_system,
        zodiac_type=inputs.zodiac_type,
        ayanamsa=inputs.ayanamsa,
    )

    natal_chart = compute_chart(
        year=inputs.natal_date.year,
        month=inputs.natal_date.month,
        day=inputs.natal_date.day,
        hour=inputs.natal_date.hour,
        minute=inputs.natal_date.minute,
        second=inputs.natal_date.second,
        lat=inputs.natal_lat,
        lng=inputs.natal_lng,
        tz_offset_minutes=tz_offset_natal,
        house_system=inputs.house_system,
        zodiac_type=inputs.zodiac_type,
        ayanamsa=inputs.ayanamsa,
    )

    aspects = compute_aspects(solar_chart["planets"], natal_chart["planets"])

    utc_dt = _jd_to_datetime_utc(result["jd_ut"])
    if inputs.target_timezone:
        tzinfo = ZoneInfo(inputs.target_timezone)
        local_dt = utc_dt.replace(tzinfo=dt_timezone.utc).astimezone(tzinfo)
    else:
        local_dt = utc_dt

    avisos = []
    if inputs.natal_time_missing:
        avisos.append(
            "Hora natal não informada: casas e ângulos podem ficar imprecisos; use horário exato para maior precisão."
        )
    if not result["bracket_found"]:
        avisos.append(
            "Não foi possível encontrar um bracket seguro; instante calculado por melhor aproximação horária."
        )

    metadados = {
        "ano_alvo": inputs.target_year,
        "instante_utc": utc_dt.isoformat(),
        "instante_local": local_dt.isoformat(),
        "jd_ut": round(result["jd_ut"], 8),
        "sol_natal_longitude": round(natal_sun_lon, 6),
        "sol_retorno_longitude": round(solar_chart["planets"]["Sun"]["lon"], 6),
        "delta_longitude_graus": round(result["diff_deg"], 8),
        "engine": inputs.engine,
        "bracket_found": result["bracket_found"],
    }

    return {
        "metadados_tecnicos": metadados,
        "avisos": avisos,
        "natal": {
            "sol_signo": natal_sign["sign"],
            "sol_grau_no_signo": natal_sign["deg_in_sign"],
        },
        "mapa_revolucao": {
            "casas": solar_chart["houses"],
            "planetas": solar_chart["planets"],
            "aspectos": aspects,
        },
        "interpretacao": build_interpretation_ptbr(metadados),
    }
