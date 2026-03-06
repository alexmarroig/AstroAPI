from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from astro.ephemeris import compute_chart, compute_transits
from schemas.cosmic import CosmicDecisionRequest, CosmicDecisionResponse
from services.cosmic_decision_engine import analyze_context
from services.life_cycles import detect_life_timeline
from services.time_utils import get_tz_offset_minutes

from .common import get_auth

router = APIRouter()


def _normalize_time(time_str: str | None) -> tuple[int, int, int]:
    if not time_str:
        return (12, 0, 0)
    parts = time_str.split(":")
    if len(parts) == 2:
        h, m = parts
        return (int(h), int(m), 0)
    if len(parts) == 3:
        h, m, s = parts
        return (int(h), int(m), int(s))
    return (12, 0, 0)


def _optional_synastry_context(
    optional_person_chart: Optional[Any],
    request: Request,
) -> Optional[Dict[str, Any]]:
    if not optional_person_chart:
        return None

    try:
        birth_date = optional_person_chart.birth_date
        if not birth_date:
            return None
        year, month, day = [int(x) for x in birth_date.split("-")]
        hour, minute, second = _normalize_time(optional_person_chart.birth_time)
        local_dt = datetime(year, month, day, hour, minute, second)
        tz_offset = get_tz_offset_minutes(
            local_dt,
            optional_person_chart.timezone,
            optional_person_chart.tz_offset_minutes,
            request_id=getattr(request.state, "request_id", None),
        )
        chart = compute_chart(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=second,
            lat=optional_person_chart.lat,
            lng=optional_person_chart.lng,
            tz_offset_minutes=tz_offset,
            house_system=optional_person_chart.house_system,
            zodiac_type=optional_person_chart.zodiac_type,
            ayanamsa=optional_person_chart.ayanamsa,
        )
        return {"name": optional_person_chart.name or "Pessoa", "chart": chart}
    except Exception:
        return None


@router.post("/v1/cosmic/decision", response_model=CosmicDecisionResponse)
async def cosmic_decision(body: CosmicDecisionRequest, request: Request, auth=Depends(get_auth)):
    try:
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

        user_chart = compute_chart(
            year=body.natal_year,
            month=body.natal_month,
            day=body.natal_day,
            hour=body.natal_hour,
            minute=body.natal_minute,
            second=body.natal_second,
            lat=body.lat,
            lng=body.lng,
            tz_offset_minutes=tz_offset,
            house_system=body.house_system.value,
            zodiac_type=body.zodiac_type.value,
            ayanamsa=body.ayanamsa,
        )

        y, m, d = [int(part) for part in body.target_date.split("-")]
        current_transits = compute_transits(
            target_year=y,
            target_month=m,
            target_day=d,
            lat=body.lat,
            lng=body.lng,
            tz_offset_minutes=tz_offset,
            zodiac_type=body.zodiac_type.value,
            ayanamsa=body.ayanamsa,
        )

        life_cycles = detect_life_timeline(
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
        synastry_context = _optional_synastry_context(body.optional_person_chart, request)

        payload = analyze_context(
            user_chart=user_chart,
            current_transits=current_transits,
            question_context={"question": body.question, "question_type": body.question_type},
            active_life_cycles=life_cycles,
            synastry_context=synastry_context,
        )
        return CosmicDecisionResponse(
            current_cosmic_context=payload["current_cosmic_context"],
            key_influences=payload["key_influences"],
            reflective_guidance=payload["reflective_guidance"],
            suggested_reflection=payload["suggested_reflection"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Falha ao calcular orientacao cosmica: {exc}") from exc
