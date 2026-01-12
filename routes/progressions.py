from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request

from core.security import require_api_key_and_user
from schemas.progressions import (
    SecondaryProgressionCalculateRequest,
    SecondaryProgressionCalculateResponse,
)
from services.progressions import calculate_secondary_progressions
from services.time_utils import parse_date_yyyy_mm_dd, resolve_tz_offset

router = APIRouter()


def get_auth(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None),
):
    return require_api_key_and_user(
        authorization=authorization,
        x_user_id=x_user_id,
        request_path=request.url.path,
    )


@router.post(
    "/v1/progressions/secondary/calculate", response_model=SecondaryProgressionCalculateResponse
)
def secondary_progressions_calculate(
    body: SecondaryProgressionCalculateRequest, auth=Depends(get_auth)
):
    natal_dt = datetime(
        body.natal_year,
        body.natal_month,
        body.natal_day,
        body.natal_hour,
        body.natal_minute,
        body.natal_second,
    )
    target_year, target_month, target_day = parse_date_yyyy_mm_dd(body.target_date)
    target_dt = datetime(
        target_year,
        target_month,
        target_day,
        body.natal_hour,
        body.natal_minute,
        body.natal_second,
    )
    tz_offset_minutes = resolve_tz_offset(
        natal_dt, body.timezone, body.tz_offset_minutes, strict=body.strict_timezone
    )
    result = calculate_secondary_progressions(
        natal_dt=natal_dt,
        target_date=target_dt,
        lat=body.lat,
        lng=body.lng,
        tz_offset_minutes=tz_offset_minutes,
        house_system=body.house_system.value,
        zodiac_type=body.zodiac_type.value,
        ayanamsa=body.ayanamsa,
    )
    return SecondaryProgressionCalculateResponse(**result.__dict__)
