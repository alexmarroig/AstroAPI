from __future__ import annotations
from datetime import datetime, date as dt_date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from .common import get_auth
from schemas.notifications import NotificationsDailyResponse
from schemas.alerts import SystemAlert
from services.time_utils import get_tz_offset_minutes, parse_date_yyyy_mm_dd
from services.astro_logic import (
    get_moon_phase_key, get_moon_phase_label_pt, get_cosmic_weather_text,
    get_mercury_retrograde_alert
)
from astro.ephemeris import compute_moon_only
from core.cache import cache

router = APIRouter()

TTL_COSMIC_WEATHER_SECONDS = 6 * 3600
DEFAULT_DATE = dt_date.today().isoformat()
DEFAULT_LAT = -23.5505
DEFAULT_LNG = -46.6333
DEFAULT_TIMEZONE = "America/Sao_Paulo"

def _daily_notifications_payload(date: str, lat: float, lng: float, tz_offset_minutes: int) -> NotificationsDailyResponse:
    """Helper para construir o payload completo de notificações diárias."""
    moon = compute_moon_only(date, tz_offset_minutes=tz_offset_minutes)
    phase_key = get_moon_phase_key(moon["phase_angle_deg"])
    sign = moon["moon_sign"]
    phase_label = get_moon_phase_label_pt(phase_key)

    items: List[Dict[str, Any]] = [
        {
            "type": "cosmic_weather",
            "title": f"Lua {phase_label} em {sign}",
            "body": get_cosmic_weather_text(phase_key, sign),
        }
    ]

    mercury_alert = get_mercury_retrograde_alert(date, lat, lng, tz_offset_minutes)
    if mercury_alert:
        items.append(
            {
                "type": "system_alert",
                "title": mercury_alert.title,
                "body": mercury_alert.body,
                "technical": mercury_alert.technical,
            }
        )

    return NotificationsDailyResponse(date=date, items=items, items_ptbr=items)

@router.get("/v1/notifications/daily", response_model=NotificationsDailyResponse)
async def notifications_daily(
    request: Request,
    date: Optional[str] = Query(DEFAULT_DATE),
    lat: Optional[float] = Query(DEFAULT_LAT, ge=-89.9999, le=89.9999),
    lng: Optional[float] = Query(DEFAULT_LNG, ge=-180, le=180),
    timezone: Optional[str] = Query(DEFAULT_TIMEZONE),
    tz_offset_minutes: Optional[int] = Query(None),
    auth=Depends(get_auth)
):
    """Retorna as notificações diárias recomendadas para o usuário, baseadas no clima cósmico e alertas."""
    d = date or DEFAULT_DATE
    if not d:
        d = dt_date.today().isoformat()
    lat = DEFAULT_LAT if lat is None else lat
    lng = DEFAULT_LNG if lng is None else lng
    timezone = timezone or DEFAULT_TIMEZONE
    dt = datetime.strptime(d, "%Y-%m-%d").replace(hour=12, minute=0, second=0)
    resolved_offset = get_tz_offset_minutes(dt, timezone, tz_offset_minutes, request_id=request.state.request_id)

    cache_key = f"notif:{auth['user_id']}:{d}:{lat}:{lng}:{timezone}:{resolved_offset}"
    cached = cache.get(cache_key)
    if cached:
        return NotificationsDailyResponse(**cached)

    payload = _daily_notifications_payload(d, lat, lng, resolved_offset)
    cache.set(cache_key, payload.model_dump(), ttl_seconds=TTL_COSMIC_WEATHER_SECONDS)
    return payload
