from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from astro.i18n_ptbr import ASPECT_PTBR, PLANET_PTBR, SIGN_LOOKUP

router = APIRouter()

_ENGLISH_SIGN_KEYS = {
    "aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra",
    "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
}


def _canonical_signs_ptbr() -> dict[str, str]:
    canonical: dict[str, str] = {}
    for key in sorted(_ENGLISH_SIGN_KEYS):
        canonical[key] = SIGN_LOOKUP[key]
    return canonical


def _collect_english_strings(payload: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            found.extend(_collect_english_strings(value, f"{path}.{key}"))
        return found
    if isinstance(payload, list):
        for idx, value in enumerate(payload):
            found.extend(_collect_english_strings(value, f"{path}[{idx}]"))
        return found
    if isinstance(payload, str):
        val = payload.strip().lower()
        if val in _ENGLISH_SIGN_KEYS:
            found.append(path)
    return found


class ValidatePayload(BaseModel):
    payload: dict[str, Any]


@router.get("/v1/i18n/ptbr")
async def i18n_ptbr_catalog() -> dict[str, Any]:
    return {
        "ok": True,
        "data": {
            "signs": _canonical_signs_ptbr(),
            "planets": PLANET_PTBR,
            "aspects": ASPECT_PTBR,
        },
    }


@router.post("/v1/i18n/validate")
async def i18n_validate(body: ValidatePayload) -> dict[str, Any]:
    fields = _collect_english_strings(body.payload)
    return {
        "ok": True,
        "data": {
            "valid": len(fields) == 0,
            "non_translated_fields": fields,
        },
    }
