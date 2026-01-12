from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request

from core.security import require_api_key_and_user
from schemas.lunations import LunationCalculateRequest, LunationCalculateResponse
from services.lunations import calculate_lunation
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


@router.post("/v1/lunations/calculate", response_model=LunationCalculateResponse)
def lunations_calculate(body: LunationCalculateRequest, auth=Depends(get_auth)):
    year, month, day = parse_date_yyyy_mm_dd(body.date)
    local_dt = datetime(year, month, day, 12, 0, 0)
    tz_offset_minutes = resolve_tz_offset(
        local_dt, body.timezone, body.tz_offset_minutes, strict=body.strict_timezone
    )
    result = calculate_lunation(local_dt, tz_offset_minutes, body.timezone)
    return LunationCalculateResponse(**result.__dict__)
