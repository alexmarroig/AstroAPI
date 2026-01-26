from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Request, Query, HTTPException

from .common import get_auth
from schemas.chart import NatalChartRequest, RenderDataRequest
from schemas.transits import TransitsRequest
from core.cache import cache
from core.plans import is_trial_or_premium
from astro.ephemeris import compute_chart, compute_transits, PLANETS
from astro.aspects import get_aspects_profile, compute_transit_aspects
from astro.i18n_ptbr import (
    build_planets_ptbr,
    build_houses_ptbr,
    build_aspects_ptbr,
    planet_key_to_ptbr,
    sign_to_ptbr,
    format_position_ptbr,
    sign_for_longitude
)
from astro.utils import ZODIAC_SIGNS, ZODIAC_SIGNS_PT
from services.time_utils import get_tz_offset_minutes, build_time_metadata, parse_date_yyyy_mm_dd
from services.astro_logic import (
    apply_sign_localization,
    calculate_distributions,
    calculate_areas_activated,
    get_moon_phase_key,
    get_moon_phase_label_pt,
    get_cosmic_weather_text,
    apply_moon_localization,
    build_daily_summary,
    get_house_for_lon,
    angle_diff,
    RULER_MAP,
    PROFILE_DEFAULT_ORB_MAX
)
from services.i18n import is_pt_br

router = APIRouter()
logger = logging.getLogger("astro-api")

TTL_NATAL_SECONDS = 30 * 24 * 3600
TTL_TRANSITS_SECONDS = 6 * 3600
TTL_RENDER_SECONDS = 30 * 24 * 3600

@router.post("/v1/chart/natal")
async def natal(
    body: NatalChartRequest,
    request: Request,
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    """Calcula o mapa natal completo."""
    try:
        dt = datetime(body.natal_year, body.natal_month, body.natal_day,
                      body.natal_hour, body.natal_minute, body.natal_second)
        tz_offset = get_tz_offset_minutes(dt, body.timezone, body.tz_offset_minutes,
                                          strict=body.strict_timezone, request_id=request.state.request_id)

        cache_key = f"natal:{auth['user_id']}:{hash(body.model_dump_json())}:{str(lang).lower()}"
        cached = cache.get(cache_key)
        if cached: return cached

        chart = compute_chart(
            year=body.natal_year, month=body.natal_month, day=body.natal_day,
            hour=body.natal_hour, minute=body.natal_minute, second=body.natal_second,
            lat=body.lat, lng=body.lng, tz_offset_minutes=tz_offset,
            house_system=body.house_system.value, zodiac_type=body.zodiac_type.value, ayanamsa=body.ayanamsa
        )

        is_pt = is_pt_br(lang)
        chart = apply_sign_localization(chart, is_pt)
        chart.update({
            "planetas_ptbr": build_planets_ptbr(chart.get("planets", {})),
            "casas_ptbr": build_houses_ptbr(chart.get("houses", {})),
        })

        chart["metadados_tecnicos"] = {
            "idioma": "pt-BR",
            "fonte_traducao": "backend",
            **build_time_metadata(body.timezone, tz_offset, dt),
            "birth_time_precise": body.birth_time_precise
        }

        cache.set(cache_key, chart, ttl_seconds=TTL_NATAL_SECONDS)
        return chart
    except Exception as e:
        logger.error("natal_error", exc_info=True, extra={"request_id": request.state.request_id})
        raise HTTPException(status_code=500, detail=f"Erro ao calcular mapa natal: {str(e)}")

@router.post("/v1/chart/transits")
async def transits(
    body: TransitsRequest,
    request: Request,
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    """Calcula o mapa de trânsitos para uma data específica em relação ao mapa natal."""
    y, m, d = parse_date_yyyy_mm_dd(body.target_date)
    try:
        natal_dt = datetime(body.natal_year, body.natal_month, body.natal_day,
                            body.natal_hour, body.natal_minute, body.natal_second)
        tz_offset = get_tz_offset_minutes(natal_dt, body.timezone, body.tz_offset_minutes,
                                          request_id=request.state.request_id)

        cache_key = f"transits:{auth['user_id']}:{body.target_date}:{str(lang).lower()}"
        cached = cache.get(cache_key)
        if cached: return cached

        natal_chart = compute_chart(
            year=body.natal_year, month=body.natal_month, day=body.natal_day,
            hour=body.natal_hour, minute=body.natal_minute, second=body.natal_second,
            lat=body.lat, lng=body.lng, tz_offset_minutes=tz_offset,
            house_system=body.house_system.value, zodiac_type=body.zodiac_type.value, ayanamsa=body.ayanamsa
        )

        transit_chart = compute_transits(
            target_year=y, target_month=m, target_day=d,
            lat=body.lat, lng=body.lng, tz_offset_minutes=tz_offset,
            zodiac_type=body.zodiac_type.value, ayanamsa=body.ayanamsa
        )

        is_pt = is_pt_br(lang)
        natal_chart = apply_sign_localization(natal_chart, is_pt)
        transit_chart = apply_sign_localization(transit_chart, is_pt)

        aspects_profile, aspects_config = get_aspects_profile()
        aspects = compute_transit_aspects(
            transit_planets=transit_chart["planets"],
            natal_planets=natal_chart["planets"],
            aspects=aspects_config
        )

        from astro.ephemeris import compute_moon_only
        moon = compute_moon_only(body.target_date, tz_offset_minutes=tz_offset)
        phase_key = get_moon_phase_key(moon["phase_angle_deg"])
        sign = moon["moon_sign"]

        cosmic_weather = {
            "moon_phase": phase_key,
            "moon_sign": sign,
            "headline": f"Lua {get_moon_phase_label_pt(phase_key)} em {sign}",
            "text": get_cosmic_weather_text(phase_key, sign),
            "deg_in_sign": moon.get("deg_in_sign"),
        }
        cosmic_weather = apply_moon_localization(cosmic_weather, is_pt)

        response = {
            "date": body.target_date,
            "cosmic_weather": cosmic_weather,
            "cosmic_weather_ptbr": {
                "moon_phase_ptbr": get_moon_phase_label_pt(phase_key),
                "moon_sign_ptbr": sign_to_ptbr(sign),
                "headline_ptbr": cosmic_weather.get("headline"),
                "text_ptbr": cosmic_weather.get("text"),
            },
            "natal": natal_chart,
            "natal_ptbr": {
                "planetas_ptbr": build_planets_ptbr(natal_chart.get("planets", {})),
                "casas_ptbr": build_houses_ptbr(natal_chart.get("houses", {})),
            },
            "transits": transit_chart,
            "transits_ptbr": {
                "planetas_ptbr": build_planets_ptbr(transit_chart.get("planets", {})),
                "casas_ptbr": build_houses_ptbr(transit_chart.get("houses", {})),
            },
            "aspects": aspects,
            "aspectos_ptbr": build_aspects_ptbr(aspects),
            "areas_activated": calculate_areas_activated(aspects, phase_key),
            "metadados_tecnicos": {
                "perfil_aspectos": aspects_profile,
                "birth_time_precise": body.birth_time_precise,
            },
        }

        cache.set(cache_key, response, ttl_seconds=TTL_TRANSITS_SECONDS)
        return response
    except Exception as e:
        logger.error("transits_error", exc_info=True, extra={"request_id": request.state.request_id})
        raise HTTPException(status_code=500, detail=f"Erro ao calcular trânsitos: {str(e)}")

@router.post("/v1/chart/render-data")
async def render_data(
    body: RenderDataRequest,
    request: Request,
    lang: Optional[str] = Query(None, description="Idioma para nomes de signos (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    """Retorna dados simplificados e formatados para renderização visual do mapa (roda zodiacal)."""
    dt = datetime(body.year, body.month, body.day, body.hour, body.minute, body.second)
    tz_offset = get_tz_offset_minutes(dt, body.timezone, body.tz_offset_minutes, request_id=request.state.request_id)

    cache_key = f"render:{auth['user_id']}:{hash(body.model_dump_json())}:{str(lang).lower()}"
    cached = cache.get(cache_key)
    if cached: return cached

    natal = compute_chart(
        year=body.year, month=body.month, day=body.day,
        hour=body.hour, minute=body.minute, second=body.second,
        lat=body.lat, lng=body.lng, tz_offset_minutes=tz_offset,
        house_system=body.house_system.value, zodiac_type=body.zodiac_type.value, ayanamsa=body.ayanamsa
    )
    is_pt = is_pt_br(lang)
    natal = apply_sign_localization(natal, is_pt)

    cusps = natal.get("houses", {}).get("cusps")
    if not cusps or len(cusps) < 12:
        raise HTTPException(status_code=500, detail="Cálculo não retornou casas válidas.")

    houses = []
    for i in range(12):
        start = float(cusps[i])
        end = float(cusps[(i + 1) % 12])
        if end < start: end += 360.0
        houses.append({"house": i + 1, "start_deg": start, "end_deg": end})

    planets = []
    planetas_ptbr = []
    for name, p in natal.get("planets", {}).items():
        planet_data = {
            "name": name,
            "sign": p.get("sign"),
            "sign_pt": p.get("sign_pt"),
            "deg_in_sign": p.get("deg_in_sign"),
            "angle_deg": p.get("lon"),
        }
        planets.append(planet_data)

        sign_pt = sign_to_ptbr(p.get("sign", ""))
        deg_in_sign = float(p.get("deg_in_sign") or 0.0)
        planetas_ptbr.append({
            **planet_data,
            "nome_ptbr": planet_key_to_ptbr(name),
            "signo_ptbr": sign_pt,
            "grau_formatado_ptbr": format_position_ptbr(deg_in_sign, sign_pt),
        })

    zodiac = ZODIAC_SIGNS_PT if is_pt else ZODIAC_SIGNS
    casas_ptbr = [
        {
            "house": h["house"],
            "label_ptbr": f"Casa {h['house']}: {format_position_ptbr(float(h['start_deg']) % 30, sign_to_ptbr(sign_for_longitude(float(h['start_deg']))))} → {format_position_ptbr(float(h['end_deg']) % 30, sign_to_ptbr(sign_for_longitude(float(h['end_deg']))))}"
        }
        for h in houses
    ]

    resp = {
        "zodiac": zodiac,
        "houses": houses,
        "planets": planets,
        "planetas_ptbr": planetas_ptbr,
        "casas_ptbr": casas_ptbr,
        "premium_aspects": [] if is_trial_or_premium(auth["plan"]) else None,
    }

    cache.set(cache_key, resp, ttl_seconds=TTL_RENDER_SECONDS)
    return resp

@router.post("/v1/chart/distributions")
async def chart_distributions(
    body: NatalChartRequest,
    request: Request,
    auth=Depends(get_auth),
):
    """Calcula a distribuição de elementos, modalidades e planetas nas casas."""
    try:
        dt = datetime(body.natal_year, body.natal_month, body.natal_day,
                      body.natal_hour, body.natal_minute, body.natal_second)
        tz_offset = get_tz_offset_minutes(dt, body.timezone, body.tz_offset_minutes,
                                          strict=body.strict_timezone, request_id=request.state.request_id)

        chart = compute_chart(
            year=body.natal_year, month=body.natal_month, day=body.natal_day,
            hour=body.natal_hour, minute=body.natal_minute, second=body.natal_second,
            lat=body.lat, lng=body.lng, tz_offset_minutes=tz_offset,
            house_system=body.house_system.value, zodiac_type=body.zodiac_type.value, ayanamsa=body.ayanamsa
        )

        metadata = build_time_metadata(body.timezone, tz_offset, dt)
        metadata["birth_time_precise"] = body.birth_time_precise

        payload = calculate_distributions(chart, metadata=metadata)
        payload.update({
            "elements": payload.get("elementos", {}),
            "modalities": payload.get("modalidades", {}),
            "houses": payload.get("casas", []),
        })
        return payload
    except Exception as e:
        logger.error("distributions_error", exc_info=True, extra={"request_id": request.state.request_id})
        raise HTTPException(status_code=500, detail=f"Erro ao calcular distribuições: {str(e)}")

@router.post("/v1/interpretation/natal")
async def interpretation_natal(
    body: NatalChartRequest,
    request: Request,
    auth=Depends(get_auth),
):
    """Gera uma interpretação heurística simplificada do mapa natal."""
    dt = datetime(body.natal_year, body.natal_month, body.natal_day, body.natal_hour, body.natal_minute, body.natal_second)
    tz_offset = get_tz_offset_minutes(dt, body.timezone, body.tz_offset_minutes, strict=body.strict_timezone, request_id=request.state.request_id)

    chart = compute_chart(
        year=body.natal_year, month=body.natal_month, day=body.natal_day,
        hour=body.natal_hour, minute=body.natal_minute, second=body.natal_second,
        lat=body.lat, lng=body.lng, tz_offset_minutes=tz_offset,
        house_system=body.house_system.value, zodiac_type=body.zodiac_type.value, ayanamsa=body.ayanamsa
    )

    metadata = build_time_metadata(body.timezone, tz_offset, dt)
    metadata["birth_time_precise"] = body.birth_time_precise

    distributions = calculate_distributions(chart, metadata=metadata)
    planets = chart.get("planets", {})

    sun_sign = sign_to_ptbr(planets.get("Sun", {}).get("sign", ""))
    moon_sign = sign_to_ptbr(planets.get("Moon", {}).get("sign", ""))
    asc = float(chart.get("houses", {}).get("asc", 0.0))
    asc_sign = sign_to_ptbr(sign_for_longitude(asc))
    mc = float(chart.get("houses", {}).get("mc", 0.0))
    cusps = chart.get("houses", {}).get("cusps") or []

    sun_house = get_house_for_lon(cusps, float(planets.get("Sun", {}).get("lon", 0.0)))
    moon_house = get_house_for_lon(cusps, float(planets.get("Moon", {}).get("lon", 0.0)))

    ruler = RULER_MAP.get(sign_for_longitude(asc))
    ruler_house = None
    if ruler and planets.get(ruler) and planets[ruler].get("lon") is not None:
        ruler_house = get_house_for_lon(cusps, float(planets[ruler]["lon"]))

    sintese = [
        f"Sol em {sun_sign} aponta foco em temas de vida mais visíveis.",
        f"Lua em {moon_sign} indica estilo emocional e necessidades afetivas.",
        f"Ascendente em {asc_sign} sugere um jeito direto de se apresentar.",
    ]

    temas_principais = [
        {"titulo": "Foco solar", "porque": f"Sol em {sun_sign} na casa {sun_house}."},
        {"titulo": "Tom emocional", "porque": f"Lua em {moon_sign} na casa {moon_house}."},
    ]
    if ruler_house:
        temas_principais.append({"titulo": "Estilo de ação", "porque": f"Regente do Ascendente em casa {ruler_house}."})

    # Lógica de peso dos planetas (trazida do main.py)
    angular_points = [asc, mc, (asc + 180) % 360, (mc + 180) % 360]
    planet_weights = []
    for name in PLANETS.keys():
        planet = planets.get(name)
        if not planet or planet.get("lon") is None: continue
        lon = float(planet["lon"])
        house = get_house_for_lon(cusps, lon)
        angularity = min(angle_diff(lon, pt) for pt in angular_points)
        angular_score = 1.0 if angularity <= 5 else 0.4 if angularity <= 10 else 0.1
        house_score = 0.8 if house in {1, 4, 7, 10} else 0.4 if house in {2, 5, 8, 11} else 0.2
        weight = round(0.2 + angular_score + house_score, 2)
        planet_weights.append({
            "planeta": planet_key_to_ptbr(name),
            "peso": min(weight, 1.0),
            "porque": f"Casa {house} com influência de ângulos ({angularity:.1f}°)."
        })

    planet_weights.sort(key=lambda x: x["peso"], reverse=True)

    return {
        "titulo": "Resumo Geral do Mapa",
        "sintese": sintese,
        "temas_principais": temas_principais,
        "planetas_com_maior_peso": planet_weights[:3],
        "distribuicao": distributions,
        "metadados": metadata,
        "summary": " ".join(sintese),
    }
