from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

from astro.aspects import get_aspects_profile, compute_transit_aspects
from astro.ephemeris import compute_chart
from core.cache import cache
from services.astro_logic import get_house_for_lon
from services.time_utils import get_tz_offset_minutes

CHART_CACHE_TTL_SECONDS = 24 * 3600


def _normalize_time(value: str) -> Tuple[int, int, int]:
    parts = value.split(":")
    if len(parts) == 2:
        h, m = parts
        return int(h), int(m), 0
    if len(parts) == 3:
        h, m, s = parts
        return int(h), int(m), int(s)
    raise ValueError("time must be HH:MM or HH:MM:SS")


def build_chart_hash(payload: Dict[str, Any]) -> str:
    normalized = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_positions_hash(chart: Dict[str, Any]) -> str:
    planets = chart.get("planets", {})
    positions = {}
    for planet, data in sorted(planets.items()):
        positions[planet] = {
            "lon": round(float(data.get("lon", 0.0)), 6),
            "house": int(data.get("house", 0) or 0),
            "sign": str(data.get("sign", "")),
        }
    payload = json.dumps(positions, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _compute_natal_aspects(planets: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    _, aspects_profile = get_aspects_profile()
    raw = compute_transit_aspects(planets, planets, aspects_profile)

    dedup: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for asp in raw:
        p1 = str(asp.get("transit_planet", ""))
        p2 = str(asp.get("natal_planet", ""))
        if not p1 or not p2 or p1 == p2:
            continue
        pair = tuple(sorted([p1, p2]))
        key = (pair[0], pair[1], str(asp.get("aspect", "")))
        current_orb = abs(float(asp.get("orb", 99.0)))
        existing = dedup.get(key)
        if existing is None or current_orb < abs(float(existing.get("orb", 99.0))):
            dedup[key] = {
                "planet1": pair[0],
                "planet2": pair[1],
                "aspect": asp.get("aspect"),
                "orb": round(current_orb, 4),
                "influence": asp.get("influence"),
            }

    return sorted(dedup.values(), key=lambda item: item["orb"])


def compute_birth_chart(input_payload: Dict[str, Any]) -> Dict[str, Any]:
    chart_hash = build_chart_hash(input_payload)
    cached = cache.get(f"modular_chart:{chart_hash}")
    if cached:
        return cached

    birth_date = datetime.strptime(input_payload["date"], "%Y-%m-%d")
    hour, minute, second = _normalize_time(input_payload["time"])
    local_dt = datetime(
        birth_date.year,
        birth_date.month,
        birth_date.day,
        hour,
        minute,
        second,
    )
    tz_offset = get_tz_offset_minutes(
        local_dt,
        input_payload.get("timezone"),
        input_payload.get("tz_offset_minutes", 0),
        request_id=None,
    )

    chart = compute_chart(
        year=birth_date.year,
        month=birth_date.month,
        day=birth_date.day,
        hour=hour,
        minute=minute,
        second=second,
        lat=float(input_payload["latitude"]),
        lng=float(input_payload["longitude"]),
        tz_offset_minutes=tz_offset,
        house_system=input_payload.get("house_system", "P"),
        zodiac_type=input_payload.get("zodiac_type", "tropical"),
        ayanamsa=input_payload.get("ayanamsa"),
    )

    planets = chart.get("planets", {})
    cusps = chart.get("houses", {}).get("cusps", [])
    for name, planet in planets.items():
        lon = float(planet.get("lon", 0.0))
        house = int(get_house_for_lon(cusps, lon)) if cusps else 1
        planet["house"] = house
        planets[name] = planet

    chart["planets"] = planets
    chart["aspects"] = _compute_natal_aspects(planets)

    payload = {"chart_hash": chart_hash, "chart": chart}
    cache.set(f"modular_chart:{chart_hash}", payload, ttl_seconds=CHART_CACHE_TTL_SECONDS)
    return payload
