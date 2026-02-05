from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Request
from .common import get_auth
from schemas.time import TimezoneResolveRequest, ValidateLocalDatetimeRequest
from services.time_utils import get_tz_offset_minutes, build_time_metadata
from services import timezone_utils

router = APIRouter()

@router.post("/v1/time/resolve-tz")
async def resolve_timezone(body: TimezoneResolveRequest, request: Request):
    """Resolve o offset de timezone para uma data/hora local específica."""
    dt = datetime(
        year=body.year,
        month=body.month,
        day=body.day,
        hour=body.hour,
        minute=body.minute,
        second=body.second,
    )
    resolved_offset = get_tz_offset_minutes(
        dt,
        body.timezone,
        fallback_minutes=None,
        strict=body.strict_birth,
        request_id=getattr(request.state, "request_id", None),
        path=request.url.path,
        prefer_fold=body.prefer_fold,
    )
    return {
        "tz_offset_minutes": resolved_offset,
        "metadados_tecnicos": {
            "idioma": "pt-BR",
            "fonte_traducao": "backend",
            **build_time_metadata(
                timezone_name=body.timezone,
                tz_offset_minutes=resolved_offset,
                local_dt=dt,
            ),
        },
    }

@router.post("/v1/time/validate-local-datetime")
async def validate_local_datetime(body: ValidateLocalDatetimeRequest):
    """Valida se uma data/hora local é válida (considerando transições de horário de verão)."""
    result = timezone_utils.validate_local_datetime(
        body.datetime_local, body.timezone, strict=body.strict
    )
    warnings = []
    if result.warning:
        warning_message = result.warning.get("message")
        if warning_message:
            warnings.append(warning_message)

    payload = {
        "input_datetime_local": result.input_datetime.isoformat(),
        "datetime_local": result.resolved_datetime.isoformat(),
        "timezone": result.timezone,
        "tz_offset_minutes": result.tz_offset_minutes,
        "utc_datetime": result.utc_datetime.isoformat(),
        "fold": result.fold,
        "warning": result.warning,
        "datetime_local_usado": result.resolved_datetime.isoformat(),
        "datetime_utc_usado": result.utc_datetime.replace(tzinfo=None).isoformat(),
        "fold_usado": result.fold,
        "avisos": warnings,
        "metadados_tecnicos": {
            "idioma": "pt-BR",
            "fonte_traducao": "backend",
            "timezone": result.timezone,
            "tz_offset_minutes": result.tz_offset_minutes,
            "fold": result.fold,
        },
    }
    if result.adjustment_minutes:
        payload["metadados_tecnicos"]["ajuste_minutos"] = result.adjustment_minutes
    return payload
