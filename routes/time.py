from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from core.security import require_api_key_and_user
from schemas.time import ValidateLocalDatetimeRequest, ValidateLocalDatetimeResponse
from services.time_utils import analyze_local_datetime, parse_date_yyyy_mm_dd, parse_time_hh_mm_ss

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
    "/v1/time/validate-local-datetime", response_model=ValidateLocalDatetimeResponse
)
def validate_local_datetime(
    body: ValidateLocalDatetimeRequest, auth=Depends(get_auth)
):
    year, month, day = parse_date_yyyy_mm_dd(body.date)
    hour, minute, second = parse_time_hh_mm_ss(body.time)
    local_dt = datetime(year, month, day, hour, minute, second)

    analysis = analyze_local_datetime(local_dt, body.timezone)
    is_ambiguous = analysis["is_ambiguous"]
    is_nonexistent = analysis["is_nonexistent"]

    if body.strict and (is_ambiguous or is_nonexistent):
        detail = (
            "Horário ambíguo na transição de horário de verão."
            if is_ambiguous
            else "Horário inexistente na transição de horário de verão."
        )
        raise HTTPException(status_code=400, detail=detail)

    warnings = []
    if is_ambiguous:
        warnings.append("Horário ambíguo: informe prefer_fold ou ajuste o horário.")
    if is_nonexistent:
        warnings.append("Horário inexistente: ajuste o horário local para um período válido.")

    fold_used = 1 if (is_ambiguous and body.prefer_fold) else 0
    tzinfo = analysis["tzinfo"]
    aware_dt = local_dt.replace(tzinfo=tzinfo, fold=fold_used)
    offset = aware_dt.utcoffset()
    if offset is None:
        raise HTTPException(status_code=400, detail=f"Timezone sem offset disponível: {body.timezone}")

    utc_dt = aware_dt.astimezone(timezone.utc)
    tz_offset_minutes = int(offset.total_seconds() // 60)

    return ValidateLocalDatetimeResponse(
        ok=not is_nonexistent,
        local_datetime=local_dt.isoformat(),
        utc_datetime=utc_dt.replace(tzinfo=None).isoformat(),
        tz_offset_minutes=tz_offset_minutes,
        is_ambiguous=is_ambiguous,
        is_nonexistent=is_nonexistent,
        fold_used=fold_used,
        warnings=warnings,
    )
