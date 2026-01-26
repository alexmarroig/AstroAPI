from __future__ import annotations
import logging
from datetime import datetime, timedelta, date as dt_date
from typing import Optional, List, Dict, Any, Literal
from fastapi import APIRouter, Depends, Request, Query, HTTPException

from .common import get_auth
from schemas.transits import (
    TransitsEventsRequest, TransitEventsResponse, TransitsRequest,
    PreferenciasPerfil, TransitsLiveRequest
)
from core.cache import cache
from astro.ephemeris import compute_chart, compute_transits
from astro.aspects import resolve_aspects_config, compute_transit_aspects, get_aspects_profile
from services.time_utils import get_tz_offset_minutes, build_time_metadata, parse_date_yyyy_mm_dd
from services.astro_logic import (
    apply_profile_defaults,
    apply_sign_localization,
    build_transit_event,
    curate_daily_events,
    calculate_areas_activated,
    get_strength_from_score,
    get_icon_for_tags,
    PROFILE_DEFAULT_ORB_MAX,
    get_moon_phase_key,
    get_moon_phase_label_pt,
    get_cosmic_weather_text,
    apply_moon_localization
)
from services.i18n import is_pt_br

router = APIRouter()
logger = logging.getLogger("astro-api")

TTL_TRANSITS_SECONDS = 6 * 3600
DEFAULT_DATE = dt_date.today().isoformat()
DEFAULT_LAT = -23.5505
DEFAULT_LNG = -46.6333
DEFAULT_TIMEZONE = "America/Sao_Paulo"

def _build_transits_context(
    body: TransitsRequest,
    tz_offset_minutes: int,
    is_pt: bool,
    date_override: Optional[str] = None,
    preferencias: Optional[PreferenciasPerfil] = None,
) -> Dict[str, Any]:
    """Helper para construir o contexto de trânsitos (natal, trânsitos e aspectos)."""
    target_date = date_override or body.target_date
    target_y, target_m, target_d = parse_date_yyyy_mm_dd(target_date)

    aspectos_hab, orbes, orb_max, profile = apply_profile_defaults(
        body.aspectos_habilitados, body.orbes, preferencias or body.preferencias
    )

    natal_chart = compute_chart(
        body.natal_year, body.natal_month, body.natal_day, body.natal_hour, body.natal_minute, body.natal_second,
        body.lat, body.lng, tz_offset_minutes, body.house_system.value, body.zodiac_type.value, body.ayanamsa
    )

    transit_chart = compute_transits(
        target_y, target_m, target_d, body.lat, body.lng, tz_offset_minutes, body.zodiac_type.value, body.ayanamsa
    )

    natal_chart = apply_sign_localization(natal_chart, is_pt)
    transit_chart = apply_sign_localization(transit_chart, is_pt)

    aspects_config, aspectos_usados, orbes_usados = resolve_aspects_config(aspectos_hab, orbes)
    aspects = compute_transit_aspects(transit_chart["planets"], natal_chart["planets"], aspects_config)

    return {
        "natal": natal_chart, "transits": transit_chart, "aspects": aspects,
        "aspectos_usados": aspectos_usados, "orbes_usados": orbes_usados,
        "orb_max": orb_max, "profile": profile,
    }

@router.post("/v1/transits/events", response_model=TransitEventsResponse)
async def transits_events(
    body: TransitsEventsRequest,
    request: Request,
    lang: Optional[str] = Query(None, description="Idioma (ex.: pt-BR)"),
    auth=Depends(get_auth),
):
    """Calcula eventos de trânsito detalhados para um intervalo de até 30 dias."""
    try:
        natal_dt = datetime(body.natal_year, body.natal_month, body.natal_day, body.natal_hour, body.natal_minute, body.natal_second)
        tz_offset = get_tz_offset_minutes(natal_dt, body.timezone, body.tz_offset_minutes, strict=body.strict_timezone, request_id=request.state.request_id)

        start_date = datetime.strptime(body.range.from_, "%Y-%m-%d")
        end_date = datetime.strptime(body.range.to, "%Y-%m-%d")
        interval_days = (end_date - start_date).days + 1
        if interval_days > 30: raise HTTPException(status_code=400, detail="Intervalo máximo de 30 dias.")

        cache_key = f"transit-events:{auth['user_id']}:{hash(body.model_dump_json())}:{str(lang).lower()}"
        cached = cache.get(cache_key)
        if cached: return cached

        events = []
        is_pt = is_pt_br(lang)
        first_context = None
        for i in range(interval_days):
            date_str = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            context = _build_transits_context(body, tz_offset, is_pt, date_override=date_str, preferencias=body.preferencias)
            if first_context is None: first_context = context
            for aspect in context["aspects"]:
                events.append(build_transit_event(aspect, date_str, context["natal"], context["orb_max"]))

        events.sort(key=lambda x: (x.date_range.peak_utc, -x.impact_score))
        metadata = {
            "range": {"from": body.range.from_, "to": body.range.to},
            "perfil": first_context["profile"],
            "aspectos_usados": first_context["aspectos_usados"],
            "orbes_usados": first_context["orbes_usados"],
            "birth_time_precise": body.birth_time_precise,
            **build_time_metadata(body.timezone, tz_offset, natal_dt)
        }

        payload = TransitEventsResponse(events=events, metadados=metadata, avisos=[])
        cache.set(cache_key, payload.model_dump(), ttl_seconds=TTL_TRANSITS_SECONDS)
        return payload
    except Exception as e:
        logger.error("transits_events_error", exc_info=True, extra={"request_id": request.state.request_id})
        raise HTTPException(status_code=500, detail="Erro interno ao calcular eventos de trânsito.")

@router.get("/v1/transits/next-days")
async def transits_next_days(
    request: Request,
    date: Optional[str] = None,
    days: int = Query(7, ge=1, le=30),
    timezone: Optional[str] = Query(None),
    tz_offset_minutes: Optional[int] = Query(None),
    natal_year: Optional[int] = Query(None, ge=1800, le=2100),
    natal_month: Optional[int] = Query(None, ge=1, le=12),
    natal_day: Optional[int] = Query(None, ge=1, le=31),
    natal_hour: Optional[int] = Query(None, ge=0, le=23),
    natal_minute: int = Query(0, ge=0, le=59),
    natal_second: int = Query(0, ge=0, le=59),
    lat: Optional[float] = Query(None, ge=-89.9999, le=89.9999),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    house_system: str = Query("P"),
    zodiac_type: str = Query("tropical"),
    ayanamsa: Optional[str] = Query(None),
    lang: Optional[str] = Query(None),
    auth=Depends(get_auth),
):
    """Retorna um resumo dos próximos dias, incluindo o tom dominante de cada dia."""
    try:
        from routes.cosmic_weather import _get_cosmic_weather_payload
        from schemas.common import HouseSystem, ZodiacType as ZodiacTypeSchema

        start_date = datetime.strptime(date or datetime.utcnow().strftime("%Y-%m-%d"), "%Y-%m-%d").date()
        items = []
        is_pt = is_pt_br(lang)

        for offset in range(days):
            current_date = start_date + timedelta(days=offset)
            date_str = current_date.strftime("%Y-%m-%d")

            headline = "Clima com espaço para pequenos ajustes."
            tags = []
            strength = "medium"
            icon = "✨"

            if natal_year and natal_month and natal_day and lat is not None and lng is not None:
                hour = natal_hour if natal_hour is not None else 12
                natal_dt = datetime(year=natal_year, month=natal_month, day=natal_day, hour=hour)
                tz_offset = get_tz_offset_minutes(natal_dt, timezone, tz_offset_minutes, request_id=request.state.request_id)

                transits_body = TransitsRequest(
                    natal_year=natal_year, natal_month=natal_month, natal_day=natal_day,
                    natal_hour=hour, natal_minute=natal_minute, natal_second=natal_second,
                    lat=lat, lng=lng, tz_offset_minutes=tz_offset, timezone=timezone,
                    target_date=date_str, house_system=HouseSystem(house_system),
                    zodiac_type=ZodiacTypeSchema(zodiac_type), ayanamsa=ayanamsa
                )

                context = _build_transits_context(transits_body, tz_offset, is_pt, date_override=date_str)
                events = [build_transit_event(asp, date_str, context["natal"], context["orb_max"]) for asp in context["aspects"]]
                curated = curate_daily_events(events)

                if curated and curated.get("top_event"):
                    event = curated["top_event"]
                    headline = event.copy.headline
                    tags = event.tags or []
                    strength = get_strength_from_score(event.impact_score)
                    icon = get_icon_for_tags(tags)
            else:
                cw = _get_cosmic_weather_payload(date_str, timezone, tz_offset_minutes, auth["user_id"], lang,
                                                 request_id=request.state.request_id, path=request.url.path)
                headline = cw.get("headline")
                tags = [cw.get("moon_sign")] if cw.get("moon_sign") else []
                icon = "🌙"
                strength = "low"

            items.append({
                "date": date_str,
                "headline": headline,
                "tags": tags,
                "icon": icon,
                "strength": strength,
            })

        return {"days": items}
    except Exception as e:
        logger.error("transits_next_days_error", exc_info=True, extra={"request_id": request.state.request_id})
        raise HTTPException(status_code=500, detail="Erro ao carregar próximos dias.")

@router.get("/v1/transits/personal-today")
async def transits_personal_today(
    request: Request,
    date: Optional[str] = Query(DEFAULT_DATE),
    timezone: Optional[str] = Query(DEFAULT_TIMEZONE),
    tz_offset_minutes: Optional[int] = Query(None),
    natal_year: int = Query(...),
    natal_month: int = Query(...),
    natal_day: int = Query(...),
    natal_hour: Optional[int] = Query(None),
    lat: Optional[float] = Query(DEFAULT_LAT),
    lng: Optional[float] = Query(DEFAULT_LNG),
    lang: Optional[str] = Query(None),
    auth=Depends(get_auth),
):
    """Retorna os trânsitos pessoais detalhados para o dia de hoje."""
    d = date or DEFAULT_DATE
    if not d:
        d = dt_date.today().isoformat()
    lat = DEFAULT_LAT if lat is None else lat
    lng = DEFAULT_LNG if lng is None else lng
    timezone = timezone or DEFAULT_TIMEZONE
    is_pt = is_pt_br(lang)

    hour = natal_hour if natal_hour is not None else 12
    natal_dt = datetime(year=natal_year, month=natal_month, day=natal_day, hour=hour)
    tz_offset = get_tz_offset_minutes(natal_dt, timezone, tz_offset_minutes, request_id=request.state.request_id)

    transits_body = TransitsRequest(
        natal_year=natal_year, natal_month=natal_month, natal_day=natal_day, natal_hour=hour,
        lat=lat, lng=lng, tz_offset_minutes=tz_offset, timezone=timezone, target_date=d
    )

    context = _build_transits_context(transits_body, tz_offset, is_pt, date_override=d)
    events = []
    for aspect in context["aspects"]:
        events.append(build_transit_event(aspect, d, context["natal"], context["orb_max"]))

    events.sort(key=lambda x: x.impact_score, reverse=True)

    area_map = {
        "Sun": "identidade", "Moon": "emoções", "Mercury": "comunicação",
        "Venus": "relacionamentos", "Mars": "trabalho", "Jupiter": "expansão",
        "Saturn": "responsabilidade", "Uranus": "mudanças", "Neptune": "sensibilidade",
        "Pluto": "transformação",
    }

    personal_transits = []
    for event in events[:8]:
        # Tenta mapear o alvo (planeta em inglês) para a área
        # Nota: event.alvo aqui está em PT-BR, precisamos do nome original ou mapear em PT-BR
        # Como event.alvo é planet_key_to_ptbr(natal_planet), vamos usar um mapa em PT-BR
        area_map_pt = {
            "Sol": "identidade", "Lua": "emoções", "Mercúrio": "comunicação",
            "Vênus": "relacionamentos", "Marte": "trabalho", "Júpiter": "expansão",
            "Saturno": "responsabilidade", "Urano": "mudanças", "Netuno": "sensibilidade",
            "Plutão": "transformação",
        }

        personal_transits.append({
            "type": event.aspecto, "transiting_planet": event.transitando,
            "natal_point": event.alvo, "orb": event.orb_graus,
            "area": area_map_pt.get(event.alvo, "tema geral"),
            "strength": get_strength_from_score(event.impact_score),
            "short_text": event.copy.mecanica
        })

    return {
        "date": d, "personal_transits": personal_transits,
        "metadados": {
            "birth_time_precise": natal_hour is not None,
            **build_time_metadata(timezone, tz_offset, natal_dt)
        }
    }

@router.post("/v1/transits/live")
async def transits_live(body: TransitsLiveRequest, request: Request, auth=Depends(get_auth)):
    """Calcula trânsitos em tempo real para um momento específico."""
    target_dt = body.target_datetime
    if isinstance(target_dt, str):
        target_dt = datetime.fromisoformat(target_dt.replace("Z", "+00:00"))

    naive_dt = target_dt.replace(tzinfo=None)
    tz_offset = get_tz_offset_minutes(naive_dt, body.timezone, body.tz_offset_minutes, strict=body.strict_timezone)

    transit_chart = compute_transits(
        target_year=naive_dt.year, target_month=naive_dt.month, target_day=naive_dt.day,
        lat=body.lat, lng=body.lng, tz_offset_minutes=tz_offset,
        zodiac_type=body.zodiac_type.value, ayanamsa=body.ayanamsa
    )

    return {
        "date": naive_dt.strftime("%Y-%m-%d"),
        "target_datetime": target_dt.isoformat(),
        "tz_offset_minutes": tz_offset,
        "transits": transit_chart,
    }

@router.get("/v1/daily/summary")
async def daily_summary(
    request: Request,
    date: Optional[str] = Query(DEFAULT_DATE),
    timezone: Optional[str] = Query(DEFAULT_TIMEZONE),
    tz_offset_minutes: Optional[int] = Query(None),
    natal_year: Optional[int] = Query(None), natal_month: Optional[int] = Query(None),
    natal_day: Optional[int] = Query(None), natal_hour: Optional[int] = Query(None),
    lat: Optional[float] = Query(DEFAULT_LAT), lng: Optional[float] = Query(DEFAULT_LNG),
    lang: Optional[str] = Query(None), auth=Depends(get_auth),
):
    """Resumo diário completo, combinando clima cósmico e trânsitos pessoais se disponíveis."""
    d = date or DEFAULT_DATE
    if not d:
        d = dt_date.today().isoformat()
    lat = DEFAULT_LAT if lat is None else lat
    lng = DEFAULT_LNG if lng is None else lng
    timezone = timezone or DEFAULT_TIMEZONE
    is_pt = is_pt_br(lang)

    # Placeholder para clima cósmico
    summary = {"tom": "Dia de estabilidade.", "gatilho": "Lua em fase neutra.", "acao": "Mantenha o ritmo."}
    headline = "Clima tranquilo."
    technical_aspects = []
    areas = []
    curated = None

    if natal_year and natal_month and natal_day and lat is not None and lng is not None:
        hour = natal_hour if natal_hour is not None else 12
        natal_dt = datetime(year=natal_year, month=natal_month, day=natal_day, hour=hour)
        tz_offset = get_tz_offset_minutes(natal_dt, timezone, tz_offset_minutes, request_id=request.state.request_id)

        transits_body = TransitsRequest(
            natal_year=natal_year, natal_month=natal_month, natal_day=natal_day, natal_hour=hour,
            lat=lat, lng=lng, tz_offset_minutes=tz_offset, timezone=timezone, target_date=d
        )
        context = _build_transits_context(transits_body, tz_offset, is_pt, date_override=d)
        events = [build_transit_event(asp, d, context["natal"], context["orb_max"]) for asp in context["aspects"]]
        curated = curate_daily_events(events)
        if curated.get("summary"): summary = curated["summary"]
        if curated.get("top_event"): headline = curated["top_event"].copy.headline

        from astro.ephemeris import compute_moon_only
        moon = compute_moon_only(d, tz_offset_minutes=tz_offset)
        phase_key = get_moon_phase_key(moon["phase_angle_deg"])
        areas = calculate_areas_activated(context["aspects"], phase_key)

    return {
        "date": d, "headline": headline, "summary": summary,
        "curated_events": curated, "areas_activated": areas
    }
