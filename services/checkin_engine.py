from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from astro.aspects import compute_transit_aspects, get_aspects_profile
from astro.ephemeris import compute_chart, compute_transits
from astro.i18n_ptbr import aspect_to_ptbr, planet_key_to_ptbr, sign_to_ptbr
from services.astro_logic import get_house_for_lon
from services.time_utils import get_tz_offset_minutes

WATER_SIGNS = {"Câncer", "Escorpião", "Peixes", "Cancer", "Scorpio", "Pisces"}
STATE_LABELS = {
    "inspired": "Inspirado",
    "focused": "Focado",
    "restless": "Inquieto",
    "social": "Social",
    "reflective": "Reflexivo",
    "low_energy": "Baixa energia",
}


def _supabase_env() -> tuple[str, str]:
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE") or ""
    if not url or not service_key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY sao obrigatorios para check-in.")
    return url, service_key


async def _supabase_get_profile(user_id: str) -> Dict[str, Any]:
    url, key = _supabase_env()
    endpoint = f"{url}/rest/v1/profiles?user_id=eq.{user_id}&select=*"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.get(endpoint, headers=headers)
    response.raise_for_status()
    rows = response.json()
    if not rows:
        raise RuntimeError("Perfil do usuario nao encontrado para check-in.")
    return rows[0]


def _parse_profile_datetime(profile: Dict[str, Any]) -> tuple[datetime, int]:
    birth_date = profile.get("birth_date")
    if not birth_date:
        raise RuntimeError("Perfil sem birth_date.")
    birth_time = profile.get("birth_time") or "12:00:00"

    if len(str(birth_time).split(":")) == 2:
        birth_time = f"{birth_time}:00"

    local_dt = datetime.fromisoformat(f"{birth_date}T{birth_time}")
    tz_offset = get_tz_offset_minutes(
        local_dt,
        profile.get("timezone"),
        profile.get("tz_offset_minutes"),
        request_id=None,
    )
    return local_dt, tz_offset


def _major_transit_summary(natal_chart: Dict[str, Any], transit_chart: Dict[str, Any]) -> str:
    _, aspects_profile = get_aspects_profile()
    aspects = compute_transit_aspects(
        transit_planets=transit_chart.get("planets", {}),
        natal_planets=natal_chart.get("planets", {}),
        aspects=aspects_profile,
    )
    if not aspects:
        return "Influencia moderada, com foco em observacao e ajustes graduais."

    aspects_sorted = sorted(aspects, key=lambda item: abs(float(item.get("orb", 8.0))))
    top = aspects_sorted[0]
    t_planet = planet_key_to_ptbr(str(top.get("transit_planet", "")))
    n_planet = planet_key_to_ptbr(str(top.get("natal_planet", "")))
    asp = aspect_to_ptbr(str(top.get("aspect", "")))
    return f"{t_planet} em {asp} com seu {n_planet}."


def _build_enriched_entry(profile: Dict[str, Any], state: str) -> Dict[str, Any]:
    local_dt, tz_offset = _parse_profile_datetime(profile)
    lat = float(profile.get("lat"))
    lng = float(profile.get("lng"))
    today = datetime.utcnow().date()

    natal_chart = compute_chart(
        year=local_dt.year,
        month=local_dt.month,
        day=local_dt.day,
        hour=local_dt.hour,
        minute=local_dt.minute,
        second=local_dt.second,
        lat=lat,
        lng=lng,
        tz_offset_minutes=tz_offset,
        house_system="P",
        zodiac_type="tropical",
        ayanamsa=None,
    )
    transit_chart = compute_transits(
        target_year=today.year,
        target_month=today.month,
        target_day=today.day,
        lat=lat,
        lng=lng,
        tz_offset_minutes=tz_offset,
        zodiac_type="tropical",
        ayanamsa=None,
    )

    moon = transit_chart.get("planets", {}).get("Moon", {})
    moon_sign = sign_to_ptbr(str(moon.get("sign", "") or ""))
    moon_lon = float(moon.get("lon", 0.0))
    houses = natal_chart.get("houses", {}).get("cusps", [])
    moon_house = int(get_house_for_lon(houses, moon_lon)) if houses else 1
    transit_summary = _major_transit_summary(natal_chart, transit_chart)

    return {
        "date": today.isoformat(),
        "state": state,
        "moon_sign": moon_sign or str(moon.get("sign", "")),
        "moon_house": moon_house,
        "transit_summary": transit_summary,
    }


async def save_checkin(user_id: str, state: str) -> Dict[str, Any]:
    profile = await _supabase_get_profile(user_id)
    entry = _build_enriched_entry(profile, state)

    url, key = _supabase_env()
    endpoint = f"{url}/rest/v1/user_cosmic_checkins"
    payload = {
        "user_id": user_id,
        "date": entry["date"],
        "state": entry["state"],
        "moon_sign": entry["moon_sign"],
        "moon_house": entry["moon_house"],
        "transit_summary": entry["transit_summary"],
    }
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }
    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(endpoint, headers=headers, json=payload)
    response.raise_for_status()
    return entry


async def get_history(user_id: str, limit: int = 12) -> List[Dict[str, Any]]:
    url, key = _supabase_env()
    endpoint = (
        f"{url}/rest/v1/user_cosmic_checkins"
        f"?user_id=eq.{user_id}&select=date,state,moon_sign,moon_house,transit_summary"
        f"&order=date.desc&limit={max(1, min(limit, 60))}"
    )
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.get(endpoint, headers=headers)
    response.raise_for_status()
    return response.json()


def detect_checkin_pattern(entries: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    if len(entries) < 4:
        return None

    reflective_water = [
        item
        for item in entries
        if item.get("state") == "reflective" and str(item.get("moon_sign", "")) in WATER_SIGNS
    ]
    if len(reflective_water) >= 3:
        return {
            "pattern": "Reflexao recorrente com Lua em signos de agua",
            "observation": (
                "Voce frequentemente registra estado reflexivo quando a Lua ativa signos de agua. "
                "Isso pode indicar maior sensibilidade e necessidade de introspecao nesses dias."
            ),
        }

    focused_house_10 = [item for item in entries if item.get("state") == "focused" and int(item.get("moon_house", 0)) == 10]
    if len(focused_house_10) >= 3:
        return {
            "pattern": "Foco recorrente com Lua ativando Casa 10",
            "observation": (
                "Seu check-in mostra tendencia de foco quando a Lua passa por temas de visibilidade e responsabilidade. "
                "Observe como voce organiza prioridades nesses ciclos."
            ),
        }

    return None


def build_cosmic_context(entry: Dict[str, Any]) -> str:
    label = STATE_LABELS.get(str(entry.get("state", "")), str(entry.get("state", "")))
    return (
        f"Estado registrado: {label}. Lua em {entry.get('moon_sign')} ativando sua Casa {entry.get('moon_house')}. "
        f"Transito de destaque: {entry.get('transit_summary')}"
    )
