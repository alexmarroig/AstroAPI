from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request

from core.security import require_api_key_and_user
from astro.i18n_ptbr import build_houses_ptbr, build_planets_ptbr
from schemas.progressions import (
    SecondaryProgressionCalculateRequest,
    SecondaryProgressionCalculateResponse,
)
from services.progressions import calculate_secondary_progressions
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
    natal_local = parse_local_datetime(datetime_local=natal_dt)
    localized = localize_with_zoneinfo(
        natal_local, body.timezone, body.tz_offset_minutes, strict=body.strict_timezone
    )
    utc_dt = to_utc(localized.datetime_local, localized.tz_offset_minutes)
    result = calculate_secondary_progressions(
        natal_dt=natal_dt,
        target_date=target_dt,
        lat=body.lat,
        lng=body.lng,
        tz_offset_minutes=localized.tz_offset_minutes,
        house_system=body.house_system.value,
        zodiac_type=body.zodiac_type.value,
        ayanamsa=body.ayanamsa,
    )
    chart_ptbr = {
        "planetas_ptbr": build_planets_ptbr(result.chart.get("planets", {})),
        "casas_ptbr": build_houses_ptbr(result.chart.get("houses", {})),
    }
    return SecondaryProgressionCalculateResponse(
        **result.__dict__,
        chart_ptbr=chart_ptbr,
        timezone_resolvida=localized.timezone_resolved,
        tz_offset_minutes_usado=localized.tz_offset_minutes,
        fold_usado=localized.fold,
        datetime_local_usado=localized.datetime_local.isoformat(),
        datetime_utc_usado=utc_dt.isoformat(),
        avisos=localized.warnings,
    )
