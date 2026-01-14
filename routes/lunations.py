from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Request

from core.security import require_api_key_and_user
from schemas.lunations import LunationCalculateRequest, LunationCalculateResponse
from services.lunations import calculate_lunation
from services.time_utils import (
    localize_with_zoneinfo,
    parse_date_yyyy_mm_dd,
    parse_local_datetime,
    to_utc,
)

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


@router.post("/v1/lunations/calculate", response_model=LunationCalculateResponse)
def lunations_calculate(body: LunationCalculateRequest, auth=Depends(get_auth)):
    year, month, day = parse_date_yyyy_mm_dd(body.date)
    local_dt = parse_local_datetime(year=year, month=month, day=day, hour=12, minute=0, second=0)
    localized = localize_with_zoneinfo(
        local_dt, body.timezone, body.tz_offset_minutes, strict=body.strict_timezone
    )
    utc_dt = to_utc(localized.datetime_local, localized.tz_offset_minutes)
    result = calculate_lunation(local_dt, localized.tz_offset_minutes, body.timezone)
    return LunationCalculateResponse(
        **result.__dict__,
        timezone_resolvida=localized.timezone_resolved,
        tz_offset_minutes_usado=localized.tz_offset_minutes,
        fold_usado=localized.fold,
        datetime_local_usado=localized.datetime_local.isoformat(),
        datetime_utc_usado=utc_dt.isoformat(),
        avisos=localized.warnings,
    )
