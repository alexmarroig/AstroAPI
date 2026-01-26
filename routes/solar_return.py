from __future__ import annotations
import os
import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, Request, HTTPException

from .common import get_auth
from schemas.solar_return import (
    SolarReturnRequest, SolarReturnOverlayRequest, SolarReturnTimelineRequest,
    SolarReturnPreferencias, SolarReturnOverlayReference
)
from astro.solar_return import SolarReturnInputs, compute_solar_return_payload, solar_return_datetime
from astro.ephemeris import compute_chart, compute_transits
from astro.aspects import resolve_aspects_config, compute_transit_aspects
from astro.i18n_ptbr import planet_key_to_ptbr, aspect_to_ptbr, sign_for_longitude
from services.time_utils import (
    get_tz_offset_minutes, build_time_metadata, localize_with_zoneinfo,
    parse_local_datetime_ptbr
)
from services.astro_logic import apply_solar_return_profile, get_house_for_lon, get_impact_score, TARGET_WEIGHTS

router = APIRouter()
logger = logging.getLogger("astro-api")

@router.post("/v1/solar-return/calculate")
async def solar_return_calculate(body: SolarReturnRequest, request: Request, auth=Depends(get_auth)):
    """Calcula o instante exato da revolução solar e o mapa correspondente."""
    # Validações de Timezone
    try: ZoneInfo(body.natal.timezone)
    except ZoneInfoNotFoundError: raise HTTPException(status_code=422, detail="Timezone natal inválido.")

    target_timezone = body.alvo.timezone or body.natal.timezone
    try: ZoneInfo(target_timezone)
    except ZoneInfoNotFoundError: raise HTTPException(status_code=422, detail="Timezone alvo inválido.")

    # Parse de Data Natal
    try: natal_dt, warnings, time_missing = parse_local_datetime_ptbr(body.natal.data, body.natal.hora)
    except Exception: raise HTTPException(status_code=422, detail="Data natal inválida.")

    prefs = body.preferencias or SolarReturnPreferencias(perfil="padrao")
    engine = os.getenv("SOLAR_RETURN_ENGINE", "v1").lower()

    aspectos_hab, orbes, _, _ = apply_solar_return_profile(prefs)

    inputs = SolarReturnInputs(
        natal_date=natal_dt, natal_lat=body.natal.local.lat, natal_lng=body.natal.local.lon,
        natal_timezone=body.natal.timezone, target_year=body.alvo.ano,
        target_lat=body.alvo.local.lat, target_lng=body.alvo.local.lon,
        target_timezone=target_timezone, house_system=prefs.sistema_casas.value,
        zodiac_type=prefs.zodiaco.value, ayanamsa=prefs.ayanamsa,
        aspectos_habilitados=aspectos_hab, orbes=orbes, engine=engine,
        tz_offset_minutes=None, natal_time_missing=time_missing,
        request_id=getattr(request.state, "request_id", None)
    )

    try:
        payload = compute_solar_return_payload(inputs)
        if warnings: payload["warnings"] = warnings
        return payload
    except Exception as e:
        logger.error("solar_return_calculate_error", exc_info=True)
        raise HTTPException(status_code=422, detail=str(e))

@router.post("/v1/solar-return/overlay")
async def solar_return_overlay(body: SolarReturnOverlayRequest, request: Request, auth=Depends(get_auth)):
    """Faz a sobreposição (synastry) entre o mapa natal e o mapa da revolução solar."""
    natal_dt, warnings, time_missing = parse_local_datetime_ptbr(body.natal.data, body.natal.hora)
    localized = localize_with_zoneinfo(natal_dt, body.natal.timezone, None)
    natal_offset = localized.tz_offset_minutes

    rs_ref = body.rs or SolarReturnOverlayReference(year=body.alvo.ano)
    if rs_ref.solar_return_utc:
        solar_return_utc = datetime.fromisoformat(rs_ref.solar_return_utc.replace("Z", "+00:00")).astimezone(dt_timezone.utc).replace(tzinfo=None)
    else:
        solar_return_utc = solar_return_datetime(natal_dt, rs_ref.year or body.alvo.ano, natal_offset)

    target_timezone = body.alvo.timezone or body.natal.timezone
    target_tzinfo = ZoneInfo(target_timezone)
    sr_local_aware = solar_return_utc.replace(tzinfo=dt_timezone.utc).astimezone(target_tzinfo)
    sr_local = sr_local_aware.replace(tzinfo=None)
    target_offset = int(sr_local_aware.utcoffset().total_seconds() // 60)

    prefs = body.preferencias or SolarReturnPreferencias(perfil="padrao")
    aspectos_hab, orbes, _, perfil = apply_solar_return_profile(prefs)

    natal_chart = compute_chart(natal_dt.year, natal_dt.month, natal_dt.day, natal_dt.hour, natal_dt.minute, natal_dt.second,
                                body.natal.local.lat, body.natal.local.lon, natal_offset, prefs.sistema_casas.value, prefs.zodiaco.value, prefs.ayanamsa)

    rs_chart = compute_chart(sr_local.year, sr_local.month, sr_local.day, sr_local.hour, sr_local.minute, sr_local.second,
                             body.alvo.local.lat, body.alvo.local.lon, target_offset, prefs.sistema_casas.value, prefs.zodiaco.value, prefs.ayanamsa)

    aspects_config, _, _ = resolve_aspects_config(aspectos_hab, orbes)
    aspects = compute_transit_aspects(rs_chart["planets"], natal_chart["planets"], aspects_config)

    return {
        "rs_em_casas_natais": [{"planeta_rs": planet_key_to_ptbr(n), "casa_natal": get_house_for_lon(natal_chart["houses"]["cusps"], d["lon"])} for n, d in rs_chart["planets"].items()],
        "natal_em_casas_rs": [{"planeta_natal": planet_key_to_ptbr(n), "casa_rs": get_house_for_lon(rs_chart["houses"]["cusps"], d["lon"])} for n, d in natal_chart["planets"].items()],
        "aspectos_rs_x_natal": [{"transitando": planet_key_to_ptbr(i["transit_planet"]), "alvo": planet_key_to_ptbr(i["natal_planet"]), "aspecto": aspect_to_ptbr(i["aspect"]), "orb_graus": float(i["orb"])} for i in aspects],
        "metadados": {**build_time_metadata(target_timezone, target_offset, sr_local), "perfil": perfil}
    }

@router.post("/v1/solar-return/timeline")
async def solar_return_timeline(body: SolarReturnTimelineRequest, request: Request, auth=Depends(get_auth)):
    """Gera uma linha do tempo anual focada nos aspectos do Sol de trânsito com pontos do mapa natal."""
    natal_dt, warnings, time_missing = parse_local_datetime_ptbr(body.natal.data, body.natal.hora)
    localized = localize_with_zoneinfo(natal_dt, body.natal.timezone, None)
    natal_offset = localized.tz_offset_minutes

    prefs = body.preferencias or SolarReturnPreferencias(perfil="padrao")
    aspectos_hab, orbes, orb_max, perfil = apply_solar_return_profile(prefs)

    natal_chart = compute_chart(natal_dt.year, natal_dt.month, natal_dt.day, natal_dt.hour, natal_dt.minute, natal_dt.second,
                                body.natal.local.lat, body.natal.local.lon, natal_offset, prefs.sistema_casas.value, prefs.zodiaco.value, prefs.ayanamsa)

    targets = {
        "Sol": natal_chart["planets"]["Sun"]["lon"],
        "Lua": natal_chart["planets"]["Moon"]["lon"],
        "ASC": natal_chart["houses"]["asc"],
        "MC": natal_chart["houses"]["mc"],
    }
    aspect_angles = {
        "conjunction": {"label": "Conjunção", "angle": 0},
        "sextile": {"label": "Sextil", "angle": 60},
        "square": {"label": "Quadratura", "angle": 90},
        "trine": {"label": "Trígono", "angle": 120},
        "opposition": {"label": "Oposição", "angle": 180},
    }

    start_date = datetime(body.year, 1, 1)
    end_date = datetime(body.year, 12, 31)
    current = start_date
    items = []
    from astro.utils import angle_diff
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        transit_chart = compute_transits(current.year, current.month, current.day, body.natal.local.lat, body.natal.local.lon, natal_offset, prefs.zodiaco.value, prefs.ayanamsa)
        sun_lon = transit_chart["planets"]["Sun"]["lon"]
        for alvo, natal_lon in targets.items():
            separation = angle_diff(sun_lon, natal_lon)
            for aspecto_key, aspect_info in aspect_angles.items():
                orb = abs(separation - aspect_info["angle"])
                if orb <= orb_max:
                    score = get_impact_score("Sun", aspecto_key, alvo if alvo in TARGET_WEIGHTS else "Sun", orb, orb_max)
                    items.append({
                        "start": (current - timedelta(days=1)).strftime("%Y-%m-%d"),
                        "peak": date_str,
                        "end": (current + timedelta(days=1)).strftime("%Y-%m-%d"),
                        "method": "solar_aspects",
                        "trigger": f"Sol em {aspect_info['label']} com {alvo}",
                        "tags": ["Ano", "Direção", "Ajuste"],
                        "score": round(score, 2),
                    })
        current += timedelta(days=1)

    items.sort(key=lambda x: x["peak"])
    return {"year_timeline": items, "metadados": {"perfil": perfil, "timezone_usada": body.natal.timezone}}
