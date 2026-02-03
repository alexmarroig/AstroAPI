from __future__ import annotations
import logging
import swisseph as swe
from datetime import timedelta
from fastapi import APIRouter, Depends, Request
from .common import get_auth
from schemas.diagnostics import EphemerisCheckRequest
from services.time_utils import get_tz_offset_minutes, to_utc
from astro.ephemeris import PLANETS, compute_chart
from astro.utils import to_julian_day, angle_diff

router = APIRouter()
logger = logging.getLogger("astro-api")

@router.post("/v1/diagnostics/ephemeris-check")
async def ephemeris_check(body: EphemerisCheckRequest, request: Request, auth=Depends(get_auth)):
    """Verifica a precisão dos cálculos da efeméride em comparação com o Swiss Ephemeris direto."""
    try:
        tz_offset = get_tz_offset_minutes(body.datetime_local, body.timezone, None, request_id=request.state.request_id)
        utc_dt = to_utc(body.datetime_local, tz_offset)
        jd_ut = to_julian_day(utc_dt)

        chart = compute_chart(body.datetime_local.year, body.datetime_local.month, body.datetime_local.day,
                              body.datetime_local.hour, body.datetime_local.minute, body.datetime_local.second,
                              body.lat, body.lng, tz_offset, house_system="P")

        items = []
        for name, planet_id in PLANETS.items():
            result, _ = swe.calc_ut(jd_ut, planet_id)
            ref_lon = result[0] % 360.0
            chart_lon = float(chart["planets"][name]["lon"])
            delta = angle_diff(chart_lon, ref_lon)
            items.append({"planet": name, "chart_lon": round(chart_lon, 6), "ref_lon": round(ref_lon, 6), "delta_deg_abs": round(delta, 6)})

        return {
            "utc_datetime": utc_dt.isoformat(),
            "tz_offset_minutes": tz_offset,
            "items": items
        }
    except Exception:
        error_code = "ephemeris_check_failed"
        logger.error(
            "ephemeris_check_error",
            exc_info=True,
            extra={"request_id": request.state.request_id, "error_code": error_code},
        )
        return {
            "success": False,
            "message": "Não foi possível validar a efeméride neste momento",
        }
