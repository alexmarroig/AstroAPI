from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request

from astro.aspects import compute_transit_aspects, resolve_aspects_config
from astro.ephemeris import compute_chart, compute_transits
from schemas.forecast import PersonalForecastRequest, PersonalForecastResponse
from services.astro_logic import (
    build_transit_event,
    curate_daily_events,
    get_impact_score,
)
from services.time_utils import get_tz_offset_minutes

from .common import get_auth

router = APIRouter()


def _build_context(body: PersonalForecastRequest, date_str: str, tz_offset: int) -> Dict[str, Any]:
    natal = compute_chart(
        body.natal_year,
        body.natal_month,
        body.natal_day,
        body.natal_hour,
        body.natal_minute,
        body.natal_second,
        body.lat,
        body.lng,
        tz_offset,
        body.house_system.value,
        body.zodiac_type.value,
        body.ayanamsa,
    )
    y, m, d = [int(p) for p in date_str.split("-")]
    transit = compute_transits(y, m, d, body.lat, body.lng, tz_offset, body.zodiac_type.value, body.ayanamsa)
    aspects_config, _, _ = resolve_aspects_config(body.aspectos_habilitados, body.orbes)
    aspects = compute_transit_aspects(transit.get("planets", {}), natal.get("planets", {}), aspects_config)
    return {"natal": natal, "transit": transit, "aspects": aspects}


@router.post("/v1/forecast/personal", response_model=PersonalForecastResponse)
async def forecast_personal(body: PersonalForecastRequest, request: Request, auth=Depends(get_auth)):
    birth_dt = datetime(
        body.natal_year,
        body.natal_month,
        body.natal_day,
        body.natal_hour,
        body.natal_minute,
        body.natal_second,
    )
    tz_offset = get_tz_offset_minutes(
        birth_dt,
        body.timezone,
        body.tz_offset_minutes,
        strict=body.strict_timezone,
        request_id=getattr(request.state, "request_id", None),
    )

    base_date = datetime.strptime(body.target_date, "%Y-%m-%d").date()
    daily_influences: List[Dict[str, Any]] = []
    all_events = []

    for i in range(body.days_ahead):
        current = (base_date + timedelta(days=i)).isoformat()
        context = _build_context(body, current, tz_offset)
        events = [build_transit_event(a, current, context["natal"], 8.0) for a in context["aspects"]]
        all_events.extend(events)
        curated = curate_daily_events(events)
        top = curated.get("top_event")
        daily_influences.append(
            {
                "date": current,
                "headline": top.copy.headline if top else "Dia de integração e ajustes progressivos.",
                "summary": curated.get("summary", {}),
                "highlights": [
                    {
                        "title": e.copy.headline,
                        "impact_score": e.impact_score,
                        "severity": e.severidade,
                    }
                    for e in events[:4]
                ],
            }
        )

    sorted_events = sorted(all_events, key=lambda x: x.impact_score, reverse=True)
    weekly_themes = [
        {
            "theme": e.copy.headline,
            "psychological_theme": e.copy.mecanica,
            "practical_advice": e.copy.use_bem,
            "risk_attention": e.copy.risco,
            "impact_score": e.impact_score,
        }
        for e in sorted_events[:3]
    ]
    major_cycles = [
        {
            "title": e.copy.headline,
            "duration": "Ciclo em andamento",
            "theme": e.copy.mecanica,
            "life_area": e.copy.risco,
            "guidance": e.copy.use_bem,
            "impact_score": e.impact_score,
        }
        for e in sorted_events[:5]
        if get_impact_score(e.transitando, e.aspecto, e.alvo, e.orb_graus, 8.0) >= 60
    ]
    opportunity_windows = [
        {
            "date": d["date"],
            "window_type": "opportunity" if idx % 2 == 0 else "integration",
            "note": d["headline"],
        }
        for idx, d in enumerate(daily_influences[:4])
    ]

    return PersonalForecastResponse(
        daily_influences=daily_influences,
        weekly_themes=weekly_themes,
        major_cycles=major_cycles,
        opportunity_windows=opportunity_windows,
    )
