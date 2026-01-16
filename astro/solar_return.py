from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import logging
from typing import Callable, Dict, List, Literal, Optional
from core.timezone_utils import TimezoneResolutionError, resolve_timezone_offset

import swisseph as swe

from astro.aspects import ASPECTS
from astro.ephemeris import AYANAMSA_MAP, compute_chart, solar_return_datetime, sun_longitude_at
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
from services.time_utils import localize_with_zoneinfo, parse_local_datetime, to_utc


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

logger = logging.getLogger("astro-api")


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
    window_days: Optional[int] = None
    step_hours: Optional[int] = None
    max_iter: Optional[int] = None
    tolerance_degrees: Optional[float] = None
    tz_offset_minutes: Optional[int] = None
    natal_time_missing: bool = False
    aspectos_habilitados: Optional[List[str]] = None
    orbes: Optional[Dict[str, float]] = None
    aspects_profile: Optional[str] = None


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
    local_dt = parse_local_datetime(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        second=second,
    )
    localized = localize_with_zoneinfo(local_dt, None, tz_offset_minutes)
    utc_dt = to_utc(localized.datetime_local, localized.tz_offset_minutes)
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

    base_local_dt = parse_local_datetime(
        year=target_year,
        month=birth_month,
        day=birth_day,
        hour=12,
        minute=0,
        second=0,
    )
    base_localized = localize_with_zoneinfo(base_local_dt, None, tz_offset_minutes)
    base_utc_dt = to_utc(base_localized.datetime_local, base_localized.tz_offset_minutes)

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


def compute_solar_return_reference(
    natal_dt: datetime,
    target_year: int,
    tz_offset_minutes: int = 0,
    engine: Literal["v1", "v2"] = "v2",
) -> dict:
    solar_return_utc = solar_return_datetime(
        natal_dt=natal_dt,
        target_year=target_year,
        tz_offset_minutes=tz_offset_minutes,
        engine=engine,
    )
    natal_utc = natal_dt - timedelta(minutes=tz_offset_minutes)
    natal_lon = sun_longitude_at(natal_utc)
    return_lon = sun_longitude_at(solar_return_utc)
    delta_longitude = abs(angle_diff(return_lon, natal_lon))
    return {
        "solar_return_utc": solar_return_utc.isoformat(),
        "natal_sun_lon": round(natal_lon, 6),
        "solar_return_sun_lon": round(return_lon, 6),
        "delta_longitude": round(delta_longitude, 6),
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
    aspects = aspects or resolve_aspects()

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


def _tz_offset_minutes(
    dt: datetime,
    timezone_name: str,
    fallback_minutes: Optional[int],
    request_id: Optional[str],
    context: str,
) -> int:
    warnings: List[str] = []
    if not timezone_name:
        if fallback_minutes is None:
            logger.warning(
                "solar_return_timezone_missing",
                extra={
                    "request_id": request_id,
                    "context": context,
                    "timezone": None,
                    "local_datetime": dt.isoformat(),
                    "warnings": ["timezone_missing"],
                },
            )
            raise ValueError("Timezone não informado.")
        warnings.append("fallback_offset_used")
        utc_dt = dt - timedelta(minutes=fallback_minutes)
        logger.info(
            "solar_return_timezone_resolved",
            extra={
                "request_id": request_id,
                "context": context,
                "timezone": None,
                "offset_minutes": fallback_minutes,
                "offset_fold0_minutes": None,
                "offset_fold1_minutes": None,
                "fold": None,
                "local_datetime": dt.isoformat(),
                "utc_datetime": utc_dt.isoformat(),
                "warnings": warnings,
            },
        )
        return fallback_minutes
    try:
        tzinfo = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        logger.warning(
            "solar_return_timezone_invalid",
            extra={
                "request_id": request_id,
                "context": context,
                "timezone": timezone_name,
                "local_datetime": dt.isoformat(),
                "warnings": ["invalid_timezone"],
            },
        )
        raise ValueError(f"Timezone inválido: {timezone_name}") from exc

    if dt.tzinfo is None:
        offset_fold0 = dt.replace(tzinfo=tzinfo, fold=0).utcoffset()
        offset_fold1 = dt.replace(tzinfo=tzinfo, fold=1).utcoffset()
        offset = offset_fold0 or offset_fold1
        fold = 0 if offset_fold0 is not None else 1
        local_dt = dt
        if offset_fold0 and offset_fold1 and offset_fold0 != offset_fold1:
            warnings.append("ambiguous_time")
    else:
        offset = dt.astimezone(tzinfo).utcoffset()
        offset_fold0 = None
        offset_fold1 = None
        fold = None
        local_dt = dt.astimezone(tzinfo)

    if offset is None:
        logger.warning(
            "solar_return_timezone_offset_missing",
            extra={
                "request_id": request_id,
                "context": context,
                "timezone": timezone_name,
                "local_datetime": dt.isoformat(),
                "warnings": ["missing_offset"],
            },
        )
        raise ValueError(f"Timezone sem offset disponível: {timezone_name}")

    offset_minutes = int(offset.total_seconds() // 60)
    utc_dt = local_dt - timedelta(minutes=offset_minutes)
    logger.info(
        "solar_return_timezone_resolved",
        extra={
            "request_id": request_id,
            "context": context,
            "timezone": timezone_name,
            "offset_minutes": offset_minutes,
            "offset_fold0_minutes": int(offset_fold0.total_seconds() // 60) if offset_fold0 else None,
            "offset_fold1_minutes": int(offset_fold1.total_seconds() // 60) if offset_fold1 else None,
            "fold": fold,
            "local_datetime": local_dt.isoformat(),
            "utc_datetime": utc_dt.isoformat(),
            "warnings": warnings,
        },
    )
    return offset_minutes


def _resolve_fold_for(
    date_time: Optional[datetime],
    timezone_name: Optional[str],
    tz_offset_minutes: Optional[int],
) -> Optional[int]:
    if date_time is None or not timezone_name or tz_offset_minutes is None:
        return None
    try:
        tzinfo = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return None

    target_offset = timedelta(minutes=tz_offset_minutes)
    offset_fold0 = date_time.replace(tzinfo=tzinfo, fold=0).utcoffset()
    offset_fold1 = date_time.replace(tzinfo=tzinfo, fold=1).utcoffset()
    if offset_fold0 == target_offset:
        return 0
    if offset_fold1 == target_offset:
        return 1
    return None


def _build_time_metadata(
    *,
    timezone_name: Optional[str],
    tz_offset_minutes: Optional[int],
    local_dt: Optional[datetime],
    avisos: Optional[List[str]] = None,
) -> Dict[str, Optional[object]]:
    utc_dt = (
        local_dt - timedelta(minutes=tz_offset_minutes)
        if local_dt is not None and tz_offset_minutes is not None
        else None
    )
    return {
        "timezone_resolvida": timezone_name,
        "tz_offset_minutes_usado": tz_offset_minutes,
        "fold_usado": _resolve_fold_for(local_dt, timezone_name, tz_offset_minutes),
        "datetime_local_usado": local_dt.isoformat() if local_dt else None,
        "datetime_utc_usado": utc_dt.isoformat() if utc_dt else None,
        "avisos": avisos or [],
    }


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
            "metodo": "heuristico",
            "reason": f"Sol em destaque na casa {sun_house}.",
            "metodo": "heuristico",
        }
    )
    areas.append(
        {
            "area": house_theme_ptbr(moon_house),
            "level": "medium",
            "score": 65,
            "metodo": "heuristico",
            "reason": f"Lua ativando a casa {moon_house}.",
            "metodo": "heuristico",
        }
    )

    asc = solar_chart.get("houses", {}).get("asc", 0.0)
    mc = solar_chart.get("houses", {}).get("mc", 0.0)
    areas.append(
        {
            "area": "Direção",
            "level": "medium",
            "score": 62,
            "metodo": "heuristico",
            "reason": f"Ângulos ASC/MC em {format_position_ptbr(float(asc) % 30, sign_to_ptbr(deg_to_sign(float(asc))['sign']))} e {format_position_ptbr(float(mc) % 30, sign_to_ptbr(deg_to_sign(float(mc))['sign']))}.",
            "metodo": "heuristico",
        }
    )

    if aspects:
        top = aspects[0]
        areas.append(
            {
                "area": "Relacionamentos",
                "level": "high",
                "score": 72,
                "metodo": "heuristico",
                "reason": (
                    f"{planet_key_to_ptbr(top.get('transit_planet'))} "
                    f"{aspect_to_ptbr(top.get('aspect'))} "
                    f"{planet_key_to_ptbr(top.get('natal_planet'))}."
                ),
                "metodo": "heuristico",
            }
        )

    if len(areas) < 5:
        areas.append(
            {
                "area": "Rotina",
                "level": "medium",
                "score": 58,
                "metodo": "heuristico",
                "reason": "Equilíbrio entre demandas pessoais e objetivos anuais.",
                "metodo": "heuristico",
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
            "metodo": "heuristico",
            "descricao": f"Sol em {sun_sign} favorece foco em identidade e visibilidade.",
            "metodo": "heuristico",
        },
        {
            "titulo": "Clima emocional",
            "metodo": "heuristico",
            "descricao": f"Lua em {moon_sign} indica sensibilidade e ajustes afetivos.",
            "metodo": "heuristico",
        },
    ]
    if aspects:
        top = aspects[0]
        highlights.append(
            {
                "titulo": "Aspecto dominante",
                "metodo": "heuristico",
                "descricao": (
                    f"{planet_key_to_ptbr(top.get('transit_planet'))} "
                    f"{aspect_to_ptbr(top.get('aspect'))} "
                    f"{planet_key_to_ptbr(top.get('natal_planet'))}."
                ),
                "metodo": "heuristico",
            }
        )
    else:
        highlights.append(
            {
                "titulo": "Integração gradual",
                "metodo": "heuristico",
                "descricao": "Poucos aspectos exatos: tendência a mudanças progressivas.",
                "metodo": "heuristico",
            }
        )

    return highlights[:3]


def compute_solar_return_payload(inputs: SolarReturnInputs) -> dict:
    natal_local = parse_local_datetime(datetime_local=inputs.natal_date)
    natal_localized = localize_with_zoneinfo(
        natal_local, inputs.natal_timezone, inputs.tz_offset_minutes
    )
    natal_offset = natal_localized.tz_offset_minutes
    natal_utc = to_utc(natal_localized.datetime_local, natal_offset)

    solar_return_utc = solar_return_datetime(
        natal_dt=inputs.natal_date,
        target_year=inputs.target_year,
        tz_offset_minutes=natal_offset,
        engine=inputs.engine,
        window_days=inputs.window_days,
        step_hours=inputs.step_hours,
        max_iter=inputs.max_iter,
        tolerance_degrees=inputs.tolerance_degrees,
    )
    solar_return_metadata = {
        "metodo_refino": "padrao",
        "iteracoes": inputs.max_iter,
        "tolerancia_graus": inputs.tolerance_degrees,
        "bracket_encontrado": None,
        "janela_usada_dias": inputs.window_days,
        "passo_usado_horas": inputs.step_hours,
    }

    target_tzinfo = ZoneInfo(inputs.target_timezone)
    solar_return_local_aware = solar_return_utc.replace(tzinfo=timezone.utc).astimezone(target_tzinfo)
    solar_return_local = solar_return_local_aware.replace(tzinfo=None)
    target_offset = int(solar_return_local_aware.utcoffset().total_seconds() // 60)

    window_days = solar_return_metadata.get("janela_usada_dias", inputs.window_days)
    step_hours = solar_return_metadata.get("passo_usado_horas", inputs.step_hours)

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

    aspects_config = resolve_aspects(
        aspects_profile=inputs.aspects_profile,
        aspectos_habilitados=inputs.aspectos_habilitados,
        orbes=inputs.orbes,
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

    metodo_refino = solar_return_metadata["metodo_refino"]
    iteracoes = solar_return_metadata["iteracoes"]
    tolerancia_graus = solar_return_metadata["tolerancia_graus"]
    bracket_encontrado = solar_return_metadata["bracket_encontrado"]
    janela_usada_dias = solar_return_metadata["janela_usada_dias"]
    passo_usado_horas = solar_return_metadata["passo_usado_horas"]

    timezone_resolvida = inputs.target_timezone or None
    fold_usado = None
    datetime_local_usado = None
    datetime_utc_usado = None
    if timezone_resolvida:
        datetime_local_usado = solar_return_local.isoformat()
        datetime_utc_usado = solar_return_utc.isoformat()

    return {
        "interpretacao": {"tipo": "heuristica", "fonte": "regras_internas"},
        "metadados_tecnicos": {
            "engine": inputs.engine,
            "solar_return_utc": solar_return_utc.isoformat(),
            "solar_return_local": solar_return_local.isoformat(),
            "delta_longitude_graus": round(delta_longitude, 6),
            "diferenca_longitude_graus": round(delta_longitude, 6),
            "idioma": "pt-BR",
            "fonte_traducao": "backend",
            "tolerancia_graus": tolerancia_graus,
            "metodo_refino": metodo_refino,
            "iteracoes": iteracoes,
            **_build_time_metadata(
                timezone_name=inputs.target_timezone,
                tz_offset_minutes=target_offset,
                local_dt=solar_return_local,
            ),
            "janela_dias": window_days,
            "passo_horas": step_hours,
            "bracket_encontrado": bracket_encontrado,
            "janela_usada_dias": janela_usada_dias,
            "passo_usado_horas": passo_usado_horas,
            "timezone_resolvida": natal_localized.timezone_resolved,
            "tz_offset_minutes_usado": natal_localized.tz_offset_minutes,
            "fold_usado": natal_localized.fold,
            "datetime_local_usado": natal_localized.datetime_local.isoformat(),
            "datetime_utc_usado": natal_utc.isoformat(),
            "avisos": natal_localized.warnings,
            "aspectos_usados": list(aspects_config.keys()),
            "orbes_usados": {name: info["orb"] for name, info in aspects_config.items()},
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
