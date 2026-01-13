from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import swisseph as swe

from astro.aspects import ASPECTS, resolve_aspects_config
from astro.ephemeris import AYANAMSA_MAP, compute_chart, solar_return_datetime
from astro.i18n_ptbr import (
    aspect_to_ptbr,
    build_aspects_ptbr,
    build_houses_ptbr,
    build_planets_ptbr,
    format_position_ptbr,
    house_theme_ptbr,
    planet_key_to_ptbr,
    sign_to_ptbr,
)
from astro.utils import angle_diff, deg_to_sign, to_julian_day


ZodiacType = Literal["tropical", "sidereal"]

PLANET_PTBR = {
    "Sun": "Sol",
    "Moon": "Lua",
    "Mercury": "Mercúrio",
    "Venus": "Vênus",
    "Mars": "Marte",
    "Jupiter": "Júpiter",
    "Saturn": "Saturno",
    "Uranus": "Urano",
    "Neptune": "Netuno",
    "Pluto": "Plutão",
}

ASPECT_PTBR = {
    "conjunction": "Conjunção",
    "opposition": "Oposição",
    "square": "Quadratura",
    "trine": "Trígono",
    "sextile": "Sextil",
}


@dataclass(frozen=True)
class SolarReturnConfig:
    zodiac_type: ZodiacType = "tropical"
    ayanamsa: Optional[str] = None
    allow_sidereal: bool = False
    house_system: str = "P"
    allow_custom_house_system: bool = False


@dataclass(frozen=True)
class SolarReturnInputs:
    natal_date: datetime
    natal_lat: float
    natal_lng: float
    natal_timezone: str
    target_year: int
    target_lat: float
    target_lng: float
    target_timezone: str
    house_system: str
    zodiac_type: ZodiacType
    ayanamsa: Optional[str]
    engine: Literal["v1", "v2"]
    tz_offset_minutes: Optional[int] = None
    natal_time_missing: bool = False
    aspectos_habilitados: Optional[List[str]] = None
    orbes: Optional[Dict[str, float]] = None


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


def _tz_offset_minutes(dt: datetime, timezone_name: str, fallback_minutes: Optional[int]) -> int:
    if not timezone_name:
        if fallback_minutes is None:
            raise ValueError("Timezone não informado.")
        return fallback_minutes
    try:
        tzinfo = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Timezone inválido: {timezone_name}") from exc

    if dt.tzinfo is None:
        offset = dt.replace(tzinfo=tzinfo).utcoffset()
    else:
        offset = dt.astimezone(tzinfo).utcoffset()
    if offset is None:
        raise ValueError(f"Timezone sem offset disponível: {timezone_name}")
    return int(offset.total_seconds() // 60)


def _house_for_lon(cusps: List[float], lon: float) -> int:
    if not cusps:
        return 1
    lon_mod = lon % 360
    for idx in range(12):
        start = cusps[idx]
        end = cusps[(idx + 1) % 12]
        start_mod = start
        end_mod = end
        lon_check = lon_mod
        if end_mod < start_mod:
            end_mod += 360
            if lon_check < start_mod:
                lon_check += 360
        if start_mod <= lon_check < end_mod:
            return idx + 1
    return 12


def _build_areas_ativadas(solar_chart: dict, aspects: List[dict]) -> List[dict]:
    cusps = solar_chart.get("houses", {}).get("cusps", [])
    planets = solar_chart.get("planets", {})
    areas: List[dict] = []

    sun_lon = planets.get("Sun", {}).get("lon", 0.0)
    moon_lon = planets.get("Moon", {}).get("lon", 0.0)
    sun_house = _house_for_lon(cusps, float(sun_lon))
    moon_house = _house_for_lon(cusps, float(moon_lon))

    areas.append(
        {
            "area": house_theme_ptbr(sun_house),
            "level": "high",
            "score": 78,
            "reason": f"Sol em destaque na casa {sun_house}.",
        }
    )
    areas.append(
        {
            "area": house_theme_ptbr(moon_house),
            "level": "medium",
            "score": 65,
            "reason": f"Lua ativando a casa {moon_house}.",
        }
    )

    asc = solar_chart.get("houses", {}).get("asc", 0.0)
    mc = solar_chart.get("houses", {}).get("mc", 0.0)
    areas.append(
        {
            "area": "Direção",
            "level": "medium",
            "score": 62,
            "reason": f"Ângulos ASC/MC em {format_position_ptbr(float(asc) % 30, sign_to_ptbr(deg_to_sign(float(asc))['sign']))} e {format_position_ptbr(float(mc) % 30, sign_to_ptbr(deg_to_sign(float(mc))['sign']))}.",
        }
    )

    if aspects:
        top = aspects[0]
        areas.append(
            {
                "area": "Relacionamentos",
                "level": "high",
                "score": 72,
                "reason": (
                    f"{planet_key_to_ptbr(top.get('transit_planet'))} "
                    f"{aspect_to_ptbr(top.get('aspect'))} "
                    f"{planet_key_to_ptbr(top.get('natal_planet'))}."
                ),
            }
        )

    if len(areas) < 5:
        areas.append(
            {
                "area": "Rotina",
                "level": "medium",
                "score": 58,
                "reason": "Equilíbrio entre demandas pessoais e objetivos anuais.",
            }
        )

    return areas[:5]


def _build_destaques(solar_chart: dict, aspects: List[dict]) -> List[dict]:
    planets = solar_chart.get("planets", {})
    sun_sign = sign_to_ptbr(planets.get("Sun", {}).get("sign", ""))
    moon_sign = sign_to_ptbr(planets.get("Moon", {}).get("sign", ""))
    highlights = [
        {
            "titulo": "Tema solar do ano",
            "descricao": f"Sol em {sun_sign} favorece foco em identidade e visibilidade.",
        },
        {
            "titulo": "Clima emocional",
            "descricao": f"Lua em {moon_sign} indica sensibilidade e ajustes afetivos.",
        },
    ]
    if aspects:
        top = aspects[0]
        highlights.append(
            {
                "titulo": "Aspecto dominante",
                "descricao": (
                    f"{planet_key_to_ptbr(top.get('transit_planet'))} "
                    f"{aspect_to_ptbr(top.get('aspect'))} "
                    f"{planet_key_to_ptbr(top.get('natal_planet'))}."
                ),
            }
        )
    else:
        highlights.append(
            {
                "titulo": "Integração gradual",
                "descricao": "Poucos aspectos exatos: tendência a mudanças progressivas.",
            }
        )

    return highlights[:3]


def compute_solar_return_payload(inputs: SolarReturnInputs) -> dict:
    natal_offset = _tz_offset_minutes(
        inputs.natal_date, inputs.natal_timezone, inputs.tz_offset_minutes
    )
    solar_return_utc = solar_return_datetime(
        natal_dt=inputs.natal_date,
        target_year=inputs.target_year,
        tz_offset_minutes=natal_offset,
        engine=inputs.engine,
    )

    target_offset = _tz_offset_minutes(
        solar_return_utc.replace(tzinfo=timezone.utc),
        inputs.target_timezone,
        None,
    )
    solar_return_local = solar_return_utc + timedelta(minutes=target_offset)

    natal_chart = compute_chart(
        year=inputs.natal_date.year,
        month=inputs.natal_date.month,
        day=inputs.natal_date.day,
        hour=inputs.natal_date.hour,
        minute=inputs.natal_date.minute,
        second=inputs.natal_date.second,
        lat=inputs.natal_lat,
        lng=inputs.natal_lng,
        tz_offset_minutes=natal_offset,
        house_system=inputs.house_system,
        zodiac_type=inputs.zodiac_type,
        ayanamsa=inputs.ayanamsa,
    )

    solar_return_chart = compute_chart(
        year=solar_return_local.year,
        month=solar_return_local.month,
        day=solar_return_local.day,
        hour=solar_return_local.hour,
        minute=solar_return_local.minute,
        second=solar_return_local.second,
        lat=inputs.target_lat,
        lng=inputs.target_lng,
        tz_offset_minutes=target_offset,
        house_system=inputs.house_system,
        zodiac_type=inputs.zodiac_type,
        ayanamsa=inputs.ayanamsa,
    )

    aspects_config, aspectos_usados, orbes_usados = resolve_aspects_config(
        inputs.aspectos_habilitados,
        inputs.orbes,
    )
    aspects = compute_aspects(
        solar_return_chart["planets"],
        natal_chart["planets"],
        aspects=aspects_config,
    )

    natal_sun_lon = natal_chart["planets"]["Sun"]["lon"]
    return_sun_lon = solar_return_chart["planets"]["Sun"]["lon"]
    delta_longitude = abs(angle_diff(return_sun_lon, natal_sun_lon))

    casas_ptbr = build_houses_ptbr(solar_return_chart["houses"])
    planetas_ptbr = build_planets_ptbr(solar_return_chart["planets"])
    aspectos_ptbr = build_aspects_ptbr(aspects)
    areas_ativadas = _build_areas_ativadas(solar_return_chart, aspects)
    destaques = _build_destaques(solar_return_chart, aspects)

    metodo_refino = "bissecao" if inputs.engine == "v2" else "grade-horaria"
    iteracoes = 60 if inputs.engine == "v2" else 97

    return {
        "metadados_tecnicos": {
            "engine": inputs.engine,
            "solar_return_utc": solar_return_utc.isoformat(),
            "solar_return_local": solar_return_local.isoformat(),
            "delta_longitude_graus": round(delta_longitude, 6),
            "diferenca_longitude_graus": round(delta_longitude, 6),
            "idioma": "pt-BR",
            "fonte_traducao": "backend",
            "tolerancia_graus": 1e-6 if inputs.engine == "v2" else None,
            "metodo_refino": metodo_refino,
            "iteracoes": iteracoes,
            "aspectos_usados": aspectos_usados,
            "orbes_usados": orbes_usados,
        },
        "mapa_revolucao": {
            "planetas": solar_return_chart["planets"],
            "planetas_ptbr": planetas_ptbr,
            "casas": solar_return_chart["houses"],
            "casas_ptbr": casas_ptbr,
            "aspectos": aspects,
            "aspectos_ptbr": aspectos_ptbr,
        },
        "areas_ativadas": areas_ativadas,
        "destaques": destaques,
    }
