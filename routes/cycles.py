from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from schemas.transits import TransitsRequest
from services.life_cycles import detect_life_timeline
from services.time_utils import get_tz_offset_minutes

from .common import get_auth

router = APIRouter()


@router.post("/v1/cycles/life-timeline")
async def life_timeline(
    body: TransitsRequest,
    request: Request,
    lang: Optional[str] = Query(None),
    auth=Depends(get_auth),
):
    natal_dt = datetime(
        body.natal_year,
        body.natal_month,
        body.natal_day,
        body.natal_hour,
        body.natal_minute,
        body.natal_second,
    )
    tz_offset = get_tz_offset_minutes(
        natal_dt,
        body.timezone,
        body.tz_offset_minutes,
        strict=body.strict_timezone,
        request_id=getattr(request.state, "request_id", None),
    )
    payload = detect_life_timeline(
        natal_year=body.natal_year,
        natal_month=body.natal_month,
        natal_day=body.natal_day,
        natal_hour=body.natal_hour,
        natal_minute=body.natal_minute,
        natal_second=body.natal_second,
        lat=body.lat,
        lng=body.lng,
        tz_offset_minutes=tz_offset,
        house_system=body.house_system.value,
        zodiac_type=body.zodiac_type.value,
        ayanamsa=body.ayanamsa,
        target_date=body.target_date,
    )
    return payload
