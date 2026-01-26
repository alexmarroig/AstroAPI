from __future__ import annotations
from datetime import datetime, date as dt_date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Request
from .common import get_auth
from schemas.alerts import SystemAlert, SystemAlertsResponse
from services.time_utils import get_tz_offset_minutes, to_utc, parse_date_yyyy_mm_dd
from services.astro_logic import get_mercury_retrograde_alert
from astro.retrogrades import retrograde_alerts
from astro.i18n_ptbr import planet_key_to_ptbr

router = APIRouter()
DEFAULT_DATE = dt_date.today().isoformat()
DEFAULT_LAT = -23.5505
DEFAULT_LNG = -46.6333
DEFAULT_TIMEZONE = "America/Sao_Paulo"

@router.get("/v1/alerts/system", response_model=SystemAlertsResponse)
async def system_alerts(
    request: Request,
    date: Optional[str] = Query(DEFAULT_DATE),
    lat: Optional[float] = Query(DEFAULT_LAT, ge=-89.9999, le=89.9999),
    lng: Optional[float] = Query(DEFAULT_LNG, ge=-180, le=180),
    timezone: Optional[str] = Query(DEFAULT_TIMEZONE),
    tz_offset_minutes: Optional[int] = Query(None),
    auth=Depends(get_auth)
):
    """Retorna alertas do sistema para uma data e local (ex: Mercúrio Retrógrado)."""
    date = date or DEFAULT_DATE
    if not date:
        date = dt_date.today().isoformat()
    lat = DEFAULT_LAT if lat is None else lat
    lng = DEFAULT_LNG if lng is None else lng
    timezone = timezone or DEFAULT_TIMEZONE
    parse_date_yyyy_mm_dd(date)
    dt = datetime.strptime(date, "%Y-%m-%d").replace(hour=12, minute=0, second=0)

    tz_offset = get_tz_offset_minutes(dt, timezone, tz_offset_minutes, request_id=request.state.request_id)

    alerts = []
    mercury = get_mercury_retrograde_alert(date, lat, lng, tz_offset)
    if mercury:
        alerts.append(mercury)

    severity_map = {"low": "baixo", "medium": "médio", "high": "alto"}
    alertas_ptbr = [{
        "id": a.id,
        "severidade_ptbr": severity_map.get(a.severity, a.severity),
        "titulo_ptbr": a.title,
        "mensagem_ptbr": a.body,
        "technical": a.technical
    } for a in alerts]

    return SystemAlertsResponse(
        date=date, alerts=alerts, alertas_ptbr=alertas_ptbr, tipos_ptbr=severity_map
    )

@router.get("/v1/alerts/retrogrades")
async def retrogrades_alerts(
    request: Request, date: Optional[str] = Query(None),
    timezone: Optional[str] = Query(None), tz_offset_minutes: Optional[int] = Query(None)
):
    """Lista todos os planetas retrógrados no momento ou em uma data específica."""
    dt_ref = datetime.strptime(date, "%Y-%m-%d") if date else datetime.utcnow()
    tz_offset = get_tz_offset_minutes(dt_ref, timezone, tz_offset_minutes)
    utc_dt = to_utc(dt_ref, tz_offset)

    alerts = retrograde_alerts(utc_dt)
    retro_pt = [{"planet": a["planet"], "planet_ptbr": planet_key_to_ptbr(a["planet"]), "is_active": a["is_active"]} for a in alerts]

    return {"retrogrades": alerts, "retrogrades_ptbr": retro_pt}
