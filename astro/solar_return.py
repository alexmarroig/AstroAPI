from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional, Literal, Dict, Any

import swisseph as swe
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from astro.ephemeris import compute_chart, AYANAMSA_MAP
from astro.aspects import compute_transit_aspects
from astro.utils import deg_to_sign, to_julian_day, angle_diff


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


HOUSE_THEMES_PT = {
    1: "identidade",
    2: "finanças e valores",
    3: "comunicação e estudos",
    4: "família e base emocional",
    5: "criatividade e romances",
    6: "rotina e saúde",
    7: "parcerias e vínculos",
    8: "transformações e recursos compartilhados",
    9: "visão de mundo e viagens",
    10: "carreira e propósito público",
    11: "redes e projetos coletivos",
    12: "inconsciente e recolhimento",
}


SIGN_RULERS = {
    "Aries": "Mars",
    "Taurus": "Venus",
    "Gemini": "Mercury",
    "Cancer": "Moon",
    "Leo": "Sun",
    "Virgo": "Mercury",
    "Libra": "Venus",
    "Scorpio": "Mars",
    "Sagittarius": "Jupiter",
    "Capricorn": "Saturn",
    "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}


def _house_for_longitude(lon: float, cusps: list[float]) -> int:
    lon = _normalize_angle(lon)
    for i in range(12):
        start = cusps[i]
        end = cusps[(i + 1) % 12]
        if end < start:
            end += 360.0
        lon_cmp = lon
        if lon_cmp < start:
            lon_cmp += 360.0
        if start <= lon_cmp < end:
            return i + 1
    return 12


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
        iterations = 0
        while current <= end_jd:
            diff = abs(f(current))
            if diff < best_diff:
                best_diff = diff
                best_jd = current
            current += step
            iterations += 1
        return {
            "jd_ut": best_jd,
            "diff_deg": abs(f(best_jd)),
            "bracket_found": False,
            "iterations": iterations,
            "tolerance_deg": 1.0,
            "method": "varredura_horaria",
        }

    prev_jd = start_jd
    prev_f = f(prev_jd)
    bracket = None
    current = prev_jd + step
    iterations = 0
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
        iterations += 1

    if bracket is None:
        best_jd = center_jd
        best_diff = 360.0
        current = start_jd
        iterations = 0
        while current <= end_jd:
            diff = abs(f(current))
            if diff < best_diff:
                best_diff = diff
                best_jd = current
            current += step
            iterations += 1
        return {
            "jd_ut": best_jd,
            "diff_deg": abs(f(best_jd)),
            "bracket_found": False,
            "iterations": iterations,
            "tolerance_deg": 1.0,
            "method": "varredura_horaria_sem_bracket",
        }

    left, right = bracket
    if left == right:
        return {
            "jd_ut": left,
            "diff_deg": 0.0,
            "bracket_found": True,
            "iterations": iterations,
            "tolerance_deg": 0.0,
            "method": "bracket_exato",
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
                "iterations": iterations + 1,
                "tolerance_deg": tolerance_deg,
                "method": "bisseccao",
            }
        left_f = f(left)
        if left_f * mid_f <= 0:
            right = mid
        else:
            left = mid
        iterations += 1

    final_f = f(mid)
    return {
        "jd_ut": mid,
        "diff_deg": abs(final_f),
        "bracket_found": True,
        "iterations": iterations,
        "tolerance_deg": tolerance_deg,
        "method": "bisseccao_limite",
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


def _areas_ativadas(
    solar_chart: Dict[str, Any],
    natal_chart: Dict[str, Any],
) -> list[dict]:
    cusps = solar_chart["houses"]["cusps"]
    asc = solar_chart["houses"]["asc"]
    mc = solar_chart["houses"]["mc"]
    dsc = _normalize_angle(asc + 180.0)
    ic = _normalize_angle(mc + 180.0)

    weights: Dict[int, float] = {}
    reasons: Dict[int, list[str]] = {}
    indicators: Dict[int, list[str]] = {}

    def add_weight(house: int, weight: float, reason: str, indicator: str):
        weights[house] = min(1.0, weights.get(house, 0.0) + weight)
        reasons.setdefault(house, []).append(reason)
        indicators.setdefault(house, []).append(indicator)

    sun_house = _house_for_longitude(solar_chart["planets"]["Sun"]["lon"], cusps)
    add_weight(sun_house, 0.35, "Sol da Revolução nesta casa", "Sol")

    asc_house = _house_for_longitude(asc, cusps)
    add_weight(asc_house, 0.3, "Ascendente da Revolução", "Ascendente")

    asc_sign = deg_to_sign(asc)["sign"]
    ruler = SIGN_RULERS.get(asc_sign)
    if ruler and ruler in solar_chart["planets"]:
        ruler_house = _house_for_longitude(solar_chart["planets"][ruler]["lon"], cusps)
        add_weight(ruler_house, 0.25, "Regente do Ascendente", f"Regente do Ascendente ({ruler})")

    moon_house = _house_for_longitude(solar_chart["planets"]["Moon"]["lon"], cusps)
    add_weight(moon_house, 0.2, "Lua da Revolução nesta casa", "Lua")

    planet_counts: Dict[int, int] = {}
    for name, planet in solar_chart["planets"].items():
        house = _house_for_longitude(planet["lon"], cusps)
        planet_counts[house] = planet_counts.get(house, 0) + 1

        for angle_lon, angle_name in ((asc, "ASC"), (mc, "MC"), (dsc, "DSC"), (ic, "IC")):
            if angle_diff(planet["lon"], angle_lon) <= 5.0:
                angle_house = _house_for_longitude(angle_lon, cusps)
                add_weight(
                    angle_house,
                    0.3,
                    f"Planeta próximo ao {angle_name}",
                    f"{name} a ≤ 5° do {angle_name}",
                )

    for house, count in planet_counts.items():
        if count >= 3:
            add_weight(house, 0.3, "Concentração de planetas nesta casa", f"{count} planetas")
        elif count == 2:
            add_weight(house, 0.2, "Boa concentração de planetas nesta casa", "2 planetas")

    sorted_houses = sorted(weights.items(), key=lambda x: x[1], reverse=True)
    areas = []
    for house, weight in sorted_houses:
        tema = HOUSE_THEMES_PT.get(house, "tema não definido")
        porque = "; ".join(reasons.get(house, [])[:2]) or "Indicadores do mapa"
        areas.append(
            {
                "casa": house,
                "tema": tema,
                "peso": round(weight, 3),
                "porque": porque,
                "indicadores": indicators.get(house, []),
            }
        )

    return areas


def _destaques(areas: list[dict]) -> list[dict]:
    destaques = []
    for area in areas[:5]:
        titulo = f"Casa {area['casa']} em foco: {area['tema']}"
        porque = area["porque"]
        o_que_observar = "Observe decisões e mudanças ligadas a este tema ao longo do ano."
        destaques.append(
            {
                "titulo": titulo,
                "porque": porque,
                "o_que_observar": o_que_observar,
            }
        )
    return destaques


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
    areas = _areas_ativadas(solar_chart, natal_chart)
    destaques = _destaques(areas)

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
        "diferenca_longitude_graus": round(result["diff_deg"], 8),
        "metodo_refino": result.get("method", "desconhecido"),
        "iteracoes": result.get("iterations", 0),
        "tolerancia_graus": result.get("tolerance_deg", None),
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
        "areas_ativadas": areas,
        "destaques": destaques,
        "interpretacao": build_interpretation_ptbr(metadados),
    }
