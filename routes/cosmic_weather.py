from __future__ import annotations
import logging
from datetime import datetime, timedelta, date as dt_date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Request, Query, HTTPException

from .common import get_auth
from schemas.cosmic_weather import CosmicWeatherResponse, CosmicWeatherRangeResponse
from core.cache import cache
from astro.ephemeris import compute_moon_only
from services.time_utils import get_tz_offset_minutes, build_time_metadata, parse_date_yyyy_mm_dd
from services.astro_logic import (
    get_moon_phase_key,
    get_moon_phase_label_pt,
    get_cosmic_weather_text,
    apply_moon_localization,
    build_daily_summary
)
from services.i18n import is_pt_br

router = APIRouter()
logger = logging.getLogger("astro-api")

TTL_COSMIC_WEATHER_SECONDS = 6 * 3600
DEFAULT_DATE = dt_date.today().isoformat()
DEFAULT_LAT = -23.5505
DEFAULT_LNG = -46.6333
DEFAULT_TIMEZONE = "America/Sao_Paulo"

def _get_cosmic_weather_payload(
    date_str: str,
    timezone_name: Optional[str],
    tz_offset_minutes: Optional[int],
    user_id: str,
    lang: Optional[str] = None,
    request_id: Optional[str] = None,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    """Calcula ou recupera do cache o clima cósmico para um único dia."""
    # Validação de data
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=12, minute=0, second=0)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato inválido de data. Use YYYY-MM-DD.")

    resolved_offset = get_tz_offset_minutes(dt, timezone_name, tz_offset_minutes, request_id=request_id, path=path)

    is_pt = True if lang is None else is_pt_br(lang)
    cache_key = f"cw:{date_str}:{timezone_name}:{resolved_offset}:{str(lang).lower()}"
    cached = cache.get(cache_key)
    if cached: return cached

    from astro.i18n_ptbr import sign_to_ptbr, format_degree_ptbr
    moon = compute_moon_only(date_str, tz_offset_minutes=resolved_offset)
    phase_key = get_moon_phase_key(moon["phase_angle_deg"])
    sign = moon["moon_sign"]
    phase_label_pt = get_moon_phase_label_pt(phase_key)
    deg_in_sign = moon.get("deg_in_sign")

    payload = {
        "date": date_str,
        "moon_phase": phase_key,
        "moon_sign": sign,
        "deg_in_sign": deg_in_sign,
        "headline": f"Lua {phase_label_pt} em {sign}",
        "text": get_cosmic_weather_text(phase_key, sign),
        "top_event": None, "trigger_event": None, "secondary_events": [],
        "summary": build_daily_summary(phase_key, sign),
    }

    payload = apply_moon_localization(payload, is_pt)
    payload.update({
        "moon_phase_ptbr": phase_label_pt,
        "moon_sign_ptbr": sign_to_ptbr(sign),
        "headline_ptbr": payload.get("headline"),
        "text_ptbr": payload.get("text"),
        "moon_ptbr": {
            "signo_ptbr": sign_to_ptbr(sign),
            "fase_ptbr": phase_label_pt,
            "grau_formatado_ptbr": format_degree_ptbr(float(deg_in_sign)) if deg_in_sign is not None else None,
        },
        "metadados_tecnicos": {
            "idioma": "pt-BR", "fonte_traducao": "backend",
            **build_time_metadata(timezone_name, resolved_offset, dt)
        }
    })

    cache.set(cache_key, payload, ttl_seconds=TTL_COSMIC_WEATHER_SECONDS)
    return payload

@router.get("/v1/cosmic-weather", response_model=CosmicWeatherResponse)
async def cosmic_weather(
    request: Request,
    date: Optional[str] = Query(DEFAULT_DATE),
    timezone: Optional[str] = Query(DEFAULT_TIMEZONE),
    tz_offset_minutes: Optional[int] = Query(None),
    lang: Optional[str] = Query(None),
    auth=Depends(get_auth),
):
    """Retorna o clima cósmico geral (fase da lua, signo lunar) para uma data."""
    d = date or DEFAULT_DATE
    if not d:
        d = dt_date.today().isoformat()
    timezone = timezone or DEFAULT_TIMEZONE
    payload = _get_cosmic_weather_payload(d, timezone, tz_offset_minutes, auth["user_id"], lang,
                                          request_id=getattr(request.state, "request_id", None), path=request.url.path)
    return CosmicWeatherResponse(**payload)

@router.get("/v1/cosmic-weather/range", response_model=CosmicWeatherRangeResponse)
async def cosmic_weather_range(
    request: Request,
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    timezone: Optional[str] = Query(DEFAULT_TIMEZONE),
    tz_offset_minutes: Optional[int] = Query(None),
    lang: Optional[str] = Query(None),
    auth=Depends(get_auth),
):
    """Retorna o clima cósmico para um intervalo de datas."""
    if not from_:
        from_ = dt_date.today().isoformat()
    if not to:
        to = (dt_date.today() + timedelta(days=6)).isoformat()
    timezone = timezone or DEFAULT_TIMEZONE

    if timezone:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError:
            raise HTTPException(status_code=422, detail="Invalid timezone. Use an IANA timezone like America/Sao_Paulo.")

    try:
        start_date = datetime.strptime(from_, "%Y-%m-%d")
        end_date = datetime.strptime(to, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato inválido de data. Use YYYY-MM-DD.")

    if end_date < start_date:
        raise HTTPException(status_code=400, detail="Parâmetro 'from' deve ser anterior ou igual a 'to'.")

    interval_days = (end_date - start_date).days + 1
    if interval_days > 90:
        raise HTTPException(status_code=422, detail="Range too large. Max 90 days. Use smaller windows.")

    items = []
    items_ptbr = []
    for i in range(interval_days):
        date_str = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        payload = _get_cosmic_weather_payload(date_str, timezone, tz_offset_minutes, auth["user_id"], lang,
                                              request_id=getattr(request.state, "request_id", None), path=request.url.path)
        items.append(CosmicWeatherResponse(**payload))
        items_ptbr.append({
            **payload,
            "headline_ptbr": payload.get("headline"),
            "resumo_ptbr": payload.get("text"),
        })

    return CosmicWeatherRangeResponse(from_=from_, to=to, items=items, items_ptbr=items_ptbr)

@router.get("/v1/moon/timeline", response_model=CosmicWeatherRangeResponse)
async def moon_timeline(
    request: Request,
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    timezone: Optional[str] = Query(DEFAULT_TIMEZONE),
    tz_offset_minutes: Optional[int] = Query(None),
    lang: Optional[str] = Query(None),
    auth=Depends(get_auth),
):
    """Retorna a linha do tempo lunar (alias para cosmic-weather/range)."""
    return await cosmic_weather_range(request, from_, to, timezone, tz_offset_minutes, lang, auth)
