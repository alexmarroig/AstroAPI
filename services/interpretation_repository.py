from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import httpx


class InterpretationRepository:
    def __init__(self) -> None:
        self.supabase_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
        self.service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE") or ""

    async def _fetch_all_modules(self) -> List[Dict[str, Any]]:
        if not self.supabase_url or not self.service_key:
            return []

        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Accept": "application/json",
        }
        endpoint = (
            f"{self.supabase_url}/rest/v1/modules"
            "?select=id,type,planet,sign,house,aspect,content"
            "&order=id.asc"
            "&limit=5000"
        )
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(endpoint, headers=headers)
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            return []
        return rows

    @staticmethod
    def _normalize_aspect_key(p1: str, p2: str, aspect: str) -> str:
        pair = sorted([p1.lower(), p2.lower()])
        return f"{pair[0]}:{pair[1]}:{aspect.lower()}"

    @staticmethod
    def _content_json(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
        return {}

    async def find_modules_for_chart(self, chart: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = await self._fetch_all_modules()
        if not rows:
            return []

        planets = chart.get("planets", {})
        aspects = chart.get("aspects", [])

        planet_sign_keys = {
            (planet_name.lower(), str(planet_data.get("sign", "")).lower())
            for planet_name, planet_data in planets.items()
        }
        planet_house_keys = {
            (planet_name.lower(), int(planet_data.get("house", 0) or 0))
            for planet_name, planet_data in planets.items()
        }
        aspect_keys = {
            self._normalize_aspect_key(
                str(item.get("planet1", "")),
                str(item.get("planet2", "")),
                str(item.get("aspect", "")),
            )
            for item in aspects
        }

        matched: List[Dict[str, Any]] = []
        seen_ids = set()
        for row in rows:
            row_id = row.get("id")
            if row_id in seen_ids:
                continue

            module_type = str(row.get("type", ""))
            planet = str(row.get("planet", "") or "").lower()
            sign = str(row.get("sign", "") or "").lower()
            house_raw: Optional[int] = row.get("house")
            house = int(house_raw) if house_raw is not None else None
            aspect = str(row.get("aspect", "") or "").lower()

            is_match = False
            if module_type == "planet_sign":
                is_match = (planet, sign) in planet_sign_keys
            elif module_type == "planet_house":
                is_match = house is not None and (planet, house) in planet_house_keys
            elif module_type == "aspect":
                pair_parts = planet.split(":") if ":" in planet else []
                if len(pair_parts) == 2:
                    key = self._normalize_aspect_key(pair_parts[0], pair_parts[1], aspect)
                    is_match = key in aspect_keys

            if is_match:
                row["content"] = self._content_json(row.get("content"))
                matched.append(row)
                seen_ids.add(row_id)

        return matched
