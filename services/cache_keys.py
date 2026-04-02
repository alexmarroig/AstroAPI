import hashlib
import json
from typing import Any

ENGINE_VERSION = "v1"

def _drop_none_and_empty(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        cleaned[key] = value
    return cleaned

def _normalize_value(key: str | None, value: Any) -> Any:
    if isinstance(value, dict):
        return normalize_payload(value)
    if isinstance(value, list):
        return [
            _normalize_value(None, item)
            for item in value
            if item is not None
        ]
    if key in {"lat", "lng"}:
        try:
            return round(float(value), 6)
        except (TypeError, ValueError):
            return None
    return value

def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = _drop_none_and_empty(dict(payload))

    normalized: dict[str, Any] = {}
    for key, value in data.items():
        normalized_value = _normalize_value(key, value)
        if normalized_value is None:
            continue
        normalized[key] = normalized_value

    tz = normalized.get("timezone")
    if tz:
        normalized["timezone"] = str(tz)
        normalized.pop("tz_offset_minutes", None)
    elif "tz_offset_minutes" in normalized:
        try:
            normalized["tz_offset_minutes"] = int(normalized["tz_offset_minutes"])
        except (TypeError, ValueError):
            normalized.pop("tz_offset_minutes", None)

    for alias in (
        "birth_date",
        "birth_time",
        "birth_datetime",
        "birthDate",
        "birthTime",
        "birthDatetime",
        "birthDateTime",
    ):
        normalized.pop(alias, None)

    if "natal_year" in normalized:
        for key in ("year", "month", "day", "hour", "minute", "second"):
            normalized.pop(key, None)

    return normalized

def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def compute_input_hash(payload: dict[str, Any]) -> str:
    normalized = normalize_payload(payload)
    raw = canonical_json(normalized)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def build_period(chart_type: str, year: int | None = None, date_yyyy_mm_dd: str | None = None) -> str | None:
    if chart_type == "natal":
        return None
    if chart_type == "solar_return" and year:
        return f"SR:{year:04d}"
    if chart_type == "transits" and date_yyyy_mm_dd:
        return f"TR:{date_yyyy_mm_dd}"
    return None
