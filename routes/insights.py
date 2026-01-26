from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Request, Query, HTTPException

from .common import get_auth
from schemas.insights import MercuryRetrogradeRequest
from schemas.transits import TransitsRequest
from schemas.solar_return import SolarReturnResponse
from astro.ephemeris import compute_transits, compute_moon_only, compute_chart
from astro.aspects import get_aspects_profile, compute_transit_aspects
from astro.i18n_ptbr import planet_key_to_ptbr, sign_to_ptbr, sign_for_longitude, build_aspects_ptbr, aspect_to_ptbr
from astro.utils import angle_diff
from services.time_utils import get_tz_offset_minutes, parse_date_yyyy_mm_dd, build_time_metadata
from services.astro_logic import (
    apply_sign_localization,
    get_moon_phase_key,
    get_cosmic_weather_text,
    apply_solar_return_profile,
    get_house_for_lon,
    RULER_MAP,
    TARGET_WEIGHTS
)
from services.i18n import is_pt_br
from astro.solar_return import solar_return_datetime # Import from astro engine
import os

router = APIRouter()
logger = logging.getLogger("astro-api")

@router.post("/v1/insights/mercury-retrograde")
async def mercury_retrograde(body: MercuryRetrogradeRequest, request: Request, auth=Depends(get_auth)):
    """Informa se Mercúrio está retrógrado em uma determinada data."""
    y, m, d = parse_date_yyyy_mm_dd(body.target_date)
    dt_ref = datetime(y, m, d, 12, 0, 0)
    tz_offset = get_tz_offset_minutes(dt_ref, body.timezone, body.tz_offset_minutes, request_id=request.state.request_id)

    transit_chart = compute_transits(y, m, d, body.lat, body.lng, tz_offset_minutes=tz_offset,
                                     zodiac_type=body.zodiac_type.value, ayanamsa=body.ayanamsa)

    mercury = transit_chart["planets"]["Mercury"]
    retrograde = bool(mercury.get("retrograde"))

    return {
        "date": body.target_date,
        "status": "retrograde" if retrograde else "direct",
        "retrograde": retrograde,
        "speed": mercury.get("speed"),
        "planet": "Mercury",
        "status_ptbr": "Retrógrado" if retrograde else "Direto",
        "planeta_ptbr": "Mercúrio",
        "bullets_ptbr": [
            "Revisões e checagens ganham prioridade.",
            "Comunicações pedem clareza extra.",
            "Ajustes de cronograma ajudam a manter o ritmo.",
        ],
    }

@router.post("/v1/insights/dominant-theme")
async def dominant_theme(
    body: TransitsRequest,
    request: Request,
    lang: Optional[str] = Query(None, description="Idioma (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    """Identifica o tema astrológico dominante para o período."""
    natal_dt = datetime(body.natal_year, body.natal_month, body.natal_day, body.natal_hour, body.natal_minute, body.natal_second)
    tz_offset = get_tz_offset_minutes(natal_dt, body.timezone, body.tz_offset_minutes, request_id=request.state.request_id)

    y, m, d = parse_date_yyyy_mm_dd(body.target_date)
    natal_chart = compute_chart(body.natal_year, body.natal_month, body.natal_day, body.natal_hour, body.natal_minute, body.natal_second,
                                body.lat, body.lng, tz_offset, body.house_system.value, body.zodiac_type.value, body.ayanamsa)
    transit_chart = compute_transits(y, m, d, body.lat, body.lng, tz_offset, body.zodiac_type.value, body.ayanamsa)

    is_pt = is_pt_br(lang)
    natal_chart = apply_sign_localization(natal_chart, is_pt)
    transit_chart = apply_sign_localization(transit_chart, is_pt)

    _, aspects_config = get_aspects_profile()
    aspects = compute_transit_aspects(transit_chart["planets"], natal_chart["planets"], aspects_config)

    influence_counts: Dict[str, int] = {}
    for asp in aspects:
        inf = asp.get("influence", "Neutral")
        influence_counts[inf] = influence_counts.get(inf, 0) + 1

    if not influence_counts:
        return {
            "theme": "Quiet influence", "summary": "Poucos aspectos relevantes no período.",
            "theme_ptbr": "Influência tranquila", "summary_ptbr": "Poucos aspectos relevantes no período.",
            "bullets_ptbr": ["Clima geral mais neutro.", "Bom momento para ajustes finos.", "Atenção aos detalhes do cotidiano."]
        }

    dominant = max(influence_counts.items(), key=lambda x: x[1])[0]
    summary_map = {
        "Intense influence": "Foco em intensidade e viradas rápidas.",
        "Challenging influence": "Período de desafios e ajustes conscientes.",
        "Fluid influence": "Fluxo mais leve e oportunidades de integração.",
    }

    return {
        "theme": dominant,
        "summary": summary_map.get(dominant, "Influência predominante do período."),
        "theme_ptbr": {"Intense influence": "Influência intensa", "Challenging influence": "Influência desafiadora", "Fluid influence": "Influência fluida"}.get(dominant, "Influência predominante"),
        "summary_ptbr": summary_map.get(dominant, "Influência predominante do período."),
        "bullets_ptbr": ["Observe os padrões dos aspectos principais.", "Priorize ações alinhadas ao tom dominante.", "Ajuste expectativas conforme a intensidade do período."],
        "sample_aspects_ptbr": build_aspects_ptbr(aspects[:3])
    }

@router.post("/v1/insights/areas-activated")
async def areas_activated(body: TransitsRequest, request: Request, auth=Depends(get_auth)):
    """Analisa quais áreas da vida estão mais ativadas pelos trânsitos atuais."""
    natal_dt = datetime(body.natal_year, body.natal_month, body.natal_day, body.natal_hour, body.natal_minute, body.natal_second)
    tz_offset = get_tz_offset_minutes(natal_dt, body.timezone, body.tz_offset_minutes, request_id=request.state.request_id)

    y, m, d = parse_date_yyyy_mm_dd(body.target_date)
    natal_chart = compute_chart(body.natal_year, body.natal_month, body.natal_day, body.natal_hour, body.natal_minute, body.natal_second,
                                body.lat, body.lng, tz_offset, body.house_system.value, body.zodiac_type.value, body.ayanamsa)
    transit_chart = compute_transits(y, m, d, body.lat, body.lng, tz_offset, body.zodiac_type.value, body.ayanamsa)

    _, aspects_config = get_aspects_profile()
    aspects = compute_transit_aspects(transit_chart["planets"], natal_chart["planets"], aspects_config)

    area_map = {
        "Sun": "Identidade e propósito", "Moon": "Emoções e segurança", "Mercury": "Comunicação e estudos",
        "Venus": "Relacionamentos e afeto", "Mars": "Ação e energia", "Jupiter": "Expansão e visão",
        "Saturn": "Estrutura e responsabilidade", "Uranus": "Mudanças e liberdade",
        "Neptune": "Inspiração e sensibilidade", "Pluto": "Transformação e poder pessoal",
    }

    if not aspects:
        return {"items": [{"area": "Identidade", "score": 50}, {"area": "Relações", "score": 45}], "bullets_ptbr": ["Tendência a estabilidade."]}

    scores: Dict[str, Dict[str, Any]] = {}
    for asp in aspects:
        planet = asp.get("natal_planet")
        area = area_map.get(planet, "Tema geral")
        scores.setdefault(area, {"area": area, "score": 0, "aspects": []})
        scores[area]["score"] += {"Intense influence": 3, "Challenging influence": 2, "Fluid influence": 1}.get(asp.get("influence"), 1)
        if len(scores[area]["aspects"]) < 3: scores[area]["aspects"].append(asp)

    items = sorted(scores.values(), key=lambda x: x["score"], reverse=True)[:5]
    return {"items": items, "bullets_ptbr": ["As áreas com maior score ganham prioridade.", "Busque equilíbrio entre temas ativos."]}

@router.post("/v1/insights/care-suggestion")
async def care_suggestion(body: TransitsRequest, request: Request, lang: Optional[str] = Query(None), auth=Depends(get_auth)):
    """Fornece sugestões de autocuidado baseadas no clima astrológico."""
    y, m, d = parse_date_yyyy_mm_dd(body.target_date)
    natal_dt = datetime(body.natal_year, body.natal_month, body.natal_day, body.natal_hour, body.natal_minute, body.natal_second)
    tz_offset = get_tz_offset_minutes(natal_dt, body.timezone, body.tz_offset_minutes, request_id=request.state.request_id)

    moon = compute_moon_only(body.target_date, tz_offset_minutes=tz_offset)
    phase_key = get_moon_phase_key(moon["phase_angle_deg"])

    suggestion_map = {
        "Intense influence": "Priorize pausas e escolhas conscientes para evitar impulsos.",
        "Challenging influence": "Organize tarefas e busque apoio antes de decisões grandes.",
        "Fluid influence": "Aproveite a fluidez para avançar em projetos criativos.",
        "Neutral": "Mantenha constância e foque em rotinas simples.",
    }

    dominant_influence = "Neutral" # Seria calculado a partir dos aspectos
    return {
        "moon_phase": phase_key,
        "suggestion": suggestion_map.get(dominant_influence, "Mantenha o equilíbrio."),
        "suggestion_ptbr": suggestion_map.get(dominant_influence, "Mantenha o equilíbrio."),
        "bullets_ptbr": ["Respeite seus limites do dia.", "Ajustes pequenos geram consistência."]
    }

@router.post("/v1/insights/life-cycles")
async def life_cycles(body: TransitsRequest, request: Request, auth=Depends(get_auth)):
    """Analisa ciclos de vida importantes (como Retorno de Saturno)."""
    y, m, d = parse_date_yyyy_mm_dd(body.target_date)
    birth = datetime(body.natal_year, body.natal_month, body.natal_day, body.natal_hour, body.natal_minute, body.natal_second)
    target = datetime(y, m, d)
    age_years = (target - birth).days / 365.25

    cycles = [
        {"name": "Retorno de Saturno", "cycle_years": 29.5},
        {"name": "Retorno de Júpiter", "cycle_years": 11.86},
        {"name": "Retorno de Nodos Lunares", "cycle_years": 18.6},
    ]

    items = []
    for cycle in cycles:
        nearest = round(age_years / cycle["cycle_years"]) * cycle["cycle_years"]
        delta = age_years - nearest
        status = "active" if abs(delta) < 0.5 else "out_of_window"
        items.append({
            "cycle": cycle["name"], "approx_age_years": round(nearest, 2),
            "distance_years": round(delta, 2), "status_ptbr": "ativo" if status == "active" else "fora_da_janela"
        })

    return {"age_years": round(age_years, 2), "items": items, "bullets_ptbr": ["Ciclos indicam janelas aproximadas de ativação."]}

@router.post("/v1/insights/solar-return", response_model=SolarReturnResponse)
async def solar_return_insight(body: TransitsRequest, request: Request, auth=Depends(get_auth)):
    """Calcula o momento exato do retorno solar (revolução solar)."""
    target_y, _, _ = parse_date_yyyy_mm_dd(body.target_date)
    natal_dt = datetime(body.natal_year, body.natal_month, body.natal_day, body.natal_hour, body.natal_minute, body.natal_second)
    tz_offset = get_tz_offset_minutes(natal_dt, body.timezone, body.tz_offset_minutes, strict=body.strict_timezone, request_id=request.state.request_id)

    sr_utc = solar_return_datetime(natal_dt=natal_dt, target_year=target_y, tz_offset_minutes=tz_offset, engine=os.getenv("SOLAR_RETURN_ENGINE", "v1").lower())
    sr_local = sr_utc + timedelta(minutes=tz_offset)

    return SolarReturnResponse(
        target_year=target_y, solar_return_utc=sr_utc.isoformat(), solar_return_local=sr_local.isoformat(),
        tz_offset_minutes_usado=tz_offset, datetime_local_usado=natal_dt.isoformat(),
        idioma="pt-BR", fonte_traducao="backend"
    )
