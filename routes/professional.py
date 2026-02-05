from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from astro.ephemeris import compute_chart, compute_moon_only, compute_transits, solar_return_datetime
from astro.i18n_ptbr import PLANET_PTBR, format_degree_ptbr, sign_to_ptbr, sign_for_longitude
from core.cache import cache
from core.rbac import entitlements_for_role, resolve_role
from routes.common import get_auth
from services.lunations import calculate_lunation
from services.progressions import calculate_secondary_progressions

router = APIRouter()

I18N_SIGNS = {
    "aries": "Áries",
    "taurus": "Touro",
    "gemini": "Gêmeos",
    "cancer": "Câncer",
    "leo": "Leão",
    "virgo": "Virgem",
    "libra": "Libra",
    "scorpio": "Escorpião",
    "sagittarius": "Sagitário",
    "capricorn": "Capricórnio",
    "aquarius": "Aquário",
    "pisces": "Peixes",
}

I18N_PHASES = {
    "new_moon": "Lua Nova",
    "first_quarter": "Quarto Crescente",
    "full_moon": "Lua Cheia",
    "last_quarter": "Quarto Minguante",
}

GLYPH_IDS = {
    "Sun": "planet-sun",
    "Moon": "planet-moon",
    "Mercury": "planet-mercury",
    "Venus": "planet-venus",
    "Mars": "planet-mars",
    "Jupiter": "planet-jupiter",
    "Saturn": "planet-saturn",
    "Uranus": "planet-uranus",
    "Neptune": "planet-neptune",
    "Pluto": "planet-pluto",
}

ORACLE_DAILY_USAGE: dict[tuple[str, str], int] = {}
ORACLE_IDEMPOTENCY: dict[str, dict[str, Any]] = {}
TELEMETRY_EVENTS: list[dict[str, Any]] = []
BUG_REPORTS: list[dict[str, Any]] = []


def _ok(data: Any, *, warnings: Optional[list[str]] = None, meta: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "data": data}
    if warnings:
        payload["warnings"] = warnings
    if meta:
        payload["meta"] = meta
    return payload


def _err(code: str, message: str, *, details: Optional[Any] = None, status_code: int = 400) -> HTTPException:
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message, "details": details})


def _ptbr_planets(planets: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for name, item in planets.items():
        lon = float(item.get("lon", 0.0))
        sign_en = item.get("sign", sign_for_longitude(lon))
        out.append(
            {
                "code": name.lower(),
                "display_ptbr": PLANET_PTBR.get(name, name),
                "glyph_id": GLYPH_IDS.get(name, f"planet-{name.lower()}"),
                "longitude": round(lon, 6),
                "sign_code": str(sign_en).lower(),
                "sign_ptbr": sign_to_ptbr(sign_en),
                "deg_in_sign": round(float(item.get("deg_in_sign", 0.0)), 4),
                "position_ptbr": format_degree_ptbr(float(item.get("deg_in_sign", 0.0))),
                "retrograde": bool(item.get("retrograde", False)),
            }
        )
    return out


class AstroChartBody(BaseModel):
    year: int
    month: int
    day: int
    hour: int
    minute: int = 0
    second: int = 0
    lat: float
    lng: float
    tz_offset_minutes: int = 0
    house_system: str = "P"
    zodiac_type: str = "tropical"
    ayanamsa: Optional[str] = None


class DateRangeBody(BaseModel):
    date: str
    timezone: str = "America/Sao_Paulo"
    tz_offset_minutes: int = -180


class SolarReturnBody(AstroChartBody):
    target_year: int


class ProgressionsBody(AstroChartBody):
    target_date: str = Field(..., description="YYYY-MM-DD")




class PairChartsBody(BaseModel):
    inner: AstroChartBody
    outer: AstroChartBody

class OracleChatBody(BaseModel):
    message: str = Field(..., min_length=2)
    context: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


class TelemetryBody(BaseModel):
    event_name: str
    screen: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BugReportBody(BaseModel):
    screen: str
    action: str
    expected: str
    actual: str
    severity: str = "medium"
    device: Optional[str] = None
    app_version: Optional[str] = None
    screenshot_url: Optional[str] = None


@router.get("/v1/billing/status")
async def billing_status(auth=Depends(get_auth)):
    role = resolve_role(auth["user_id"])
    return _ok({"role": role, "plan": role, "trial_active": role == "free"})


@router.get("/v1/billing/entitlements")
async def billing_entitlements(auth=Depends(get_auth)):
    role = resolve_role(auth["user_id"])
    return _ok({"role": role, "entitlements": entitlements_for_role(role)})


@router.post("/v1/astro/chart")
async def astro_chart(body: AstroChartBody, auth=Depends(get_auth)):
    chart = compute_chart(**body.model_dump())
    return _ok({
        "chart": chart,
        "planets": _ptbr_planets(chart.get("planets", {})),
        "glyph_set": "astro-pro-v1",
    })


@router.post("/v1/astro/chart/render-spec")
async def astro_chart_render_spec(body: AstroChartBody, auth=Depends(get_auth)):
    chart = compute_chart(**body.model_dump())
    planets = _ptbr_planets(chart.get("planets", {}))
    return _ok(
        {
            "layers": ["outer-sign-ring", "house-ring", "planet-labels", "aspects"],
            "wheel": {
                "mode": "classic",
                "house_system": body.house_system,
                "zodiac_type": body.zodiac_type,
            },
            "points": planets,
            "aspects": chart.get("aspects", []),
        }
    )


@router.post("/v1/astro/transits")
async def astro_transits(body: DateRangeBody, auth=Depends(get_auth)):
    y, m, d = [int(x) for x in body.date.split("-")]
    transit = compute_transits(y, m, d, lat=-23.55, lng=-46.63, tz_offset_minutes=body.tz_offset_minutes)
    return _ok({"date": body.date, "transits": transit})


@router.post("/v1/astro/solar-return")
async def astro_solar_return(body: SolarReturnBody, auth=Depends(get_auth)):
    try:
        natal_dt = datetime(body.year, body.month, body.day, body.hour, body.minute, body.second)
        sr_utc = solar_return_datetime(natal_dt=natal_dt, target_year=body.target_year, tz_offset_minutes=body.tz_offset_minutes, engine="v2")
        sr_local = sr_utc + timedelta(minutes=body.tz_offset_minutes)
        sr_chart = compute_chart(
            year=sr_local.year,
            month=sr_local.month,
            day=sr_local.day,
            hour=sr_local.hour,
            minute=sr_local.minute,
            second=sr_local.second,
            lat=body.lat,
            lng=body.lng,
            tz_offset_minutes=body.tz_offset_minutes,
            house_system=body.house_system,
            zodiac_type=body.zodiac_type,
            ayanamsa=body.ayanamsa,
        )
        return _ok({"target_year": body.target_year, "solar_return_datetime_utc": sr_utc.isoformat(), "chart": sr_chart})
    except Exception as exc:
        _err("SOLAR_RETURN_COMPUTE_FAILED", "Não foi possível calcular a revolução solar no momento.", details=str(exc), status_code=422)


@router.post("/v1/astro/progressions")
async def astro_progressions(body: ProgressionsBody, auth=Depends(get_auth)):
    target = datetime.strptime(body.target_date, "%Y-%m-%d")
    natal = datetime(body.year, body.month, body.day, body.hour, body.minute, body.second)
    result = calculate_secondary_progressions(
        natal_dt=natal,
        target_date=target,
        lat=body.lat,
        lng=body.lng,
        tz_offset_minutes=body.tz_offset_minutes,
        house_system=body.house_system,
        zodiac_type=body.zodiac_type,
        ayanamsa=body.ayanamsa,
    )
    return _ok(result.__dict__)


@router.post("/v1/astro/synastry")
async def astro_synastry(body: PairChartsBody, auth=Depends(get_auth)):
    inner_chart = compute_chart(**body.inner.model_dump())
    outer_chart = compute_chart(**body.outer.model_dump())
    return _ok({"biwheel": True, "inner": inner_chart, "outer": outer_chart, "interaspects": []})


@router.post("/v1/astro/composite")
async def astro_composite(body: PairChartsBody, auth=Depends(get_auth)):
    a = compute_chart(**body.inner.model_dump())
    b = compute_chart(**body.outer.model_dump())
    return _ok({"composite_mode": "midpoint", "a": a, "b": b})


@router.post("/v1/astro/lunar-phases")
async def astro_lunar_phases(body: DateRangeBody, auth=Depends(get_auth)):
    cache_key = f"lunar-phases:{body.date}:{body.timezone}:{body.tz_offset_minutes}"
    cached = cache.get(cache_key)
    if cached:
        return _ok(cached, meta={"cache": "hit"})

    base = datetime.strptime(body.date, "%Y-%m-%d")
    items = []
    for i in range(30):
        current = (base + timedelta(days=i)).strftime("%Y-%m-%d")
        moon = compute_moon_only(current, tz_offset_minutes=body.tz_offset_minutes)
        lunation = calculate_lunation(datetime.strptime(current, "%Y-%m-%d"), body.tz_offset_minutes, body.timezone)
        items.append({
            "date": current,
            "phase_code": lunation.phase_key,
            "phase_ptbr": I18N_PHASES.get(lunation.phase_key, lunation.phase_key),
            "moon_sign_code": str(moon.get("moon_sign", "")).lower(),
            "moon_sign_ptbr": sign_to_ptbr(str(moon.get("moon_sign", ""))),
        })
    payload = {"items": items}
    cache.set(cache_key, payload, ttl_seconds=3600)
    return _ok(payload, meta={"cache": "miss"})


@router.post("/v1/oracle/chat")
async def oracle_chat(body: OracleChatBody, auth=Depends(get_auth)):
    user_id = auth["user_id"]
    role = resolve_role(user_id)

    if body.idempotency_key and body.idempotency_key in ORACLE_IDEMPOTENCY:
        return _ok(ORACLE_IDEMPOTENCY[body.idempotency_key], meta={"idempotent": True})

    day = datetime.utcnow().strftime("%Y-%m-%d")
    quota = 2 if role == "free" else 100000
    usage_key = (user_id, day)
    used = ORACLE_DAILY_USAGE.get(usage_key, 0)
    if used >= quota:
        _err("ORACLE_RATE_LIMIT", "Limite diário do Oráculo atingido para seu plano.", status_code=429)

    ORACLE_DAILY_USAGE[usage_key] = used + 1
    t0 = time.time()
    try:
        # fallback determinístico sempre disponível
        now = datetime.utcnow().strftime("%Y-%m-%d")
        moon = compute_moon_only(now, tz_offset_minutes=-180)
        reply = (
            f"Leitura rápida: hoje a Lua está em {sign_to_ptbr(moon.get('moon_sign',''))}. "
            "Priorize decisões práticas e observe reatividade emocional antes de agir."
        )
        response = {
            "reply": reply,
            "sources": [
                {
                    "type": "moon_sign",
                    "value": sign_to_ptbr(moon.get("moon_sign", "")),
                }
            ],
            "used_context_summary": "Fallback determinístico por aspectos do dia",
            "latency_ms": int((time.time() - t0) * 1000),
        }
        if body.idempotency_key:
            ORACLE_IDEMPOTENCY[body.idempotency_key] = response
        return _ok(response)
    except Exception as exc:
        _err("ORACLE_PROVIDER_TIMEOUT", "Serviço temporariamente indisponível. Tente novamente em instantes.", details=str(exc), status_code=503)


@router.post("/v1/telemetry/event")
async def telemetry_event(body: TelemetryBody, auth=Depends(get_auth)):
    event = {
        "event_name": body.event_name,
        "screen": body.screen,
        "user_hash": hashlib.sha256(auth["user_id"].encode()).hexdigest()[:12],
        "plan": resolve_role(auth["user_id"]),
        "metadata": body.metadata,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    TELEMETRY_EVENTS.append(event)
    return _ok({"accepted": True})


@router.post("/v1/bugs/report")
async def bugs_report(body: BugReportBody, auth=Depends(get_auth)):
    report = {
        "id": f"bug_{len(BUG_REPORTS) + 1}",
        "user_hash": hashlib.sha256(auth["user_id"].encode()).hexdigest()[:12],
        **body.model_dump(),
        "status": "open",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    BUG_REPORTS.append(report)
    return _ok(report)


@router.get("/v1/admin/dashboard")
async def admin_dashboard(auth=Depends(get_auth)):
    role = resolve_role(auth["user_id"])
    if role != "admin":
        _err("ADMIN_FORBIDDEN", "Acesso permitido apenas para administradores.", status_code=403)

    now = datetime.utcnow()
    last_30 = [(now - timedelta(days=x)).strftime("%Y-%m-%d") for x in range(30)]
    dau = len({e[0] for e in ORACLE_DAILY_USAGE.keys() if e[1] == now.strftime("%Y-%m-%d")})
    wau = len({e[0] for e in ORACLE_DAILY_USAGE.keys() if e[1] in last_30[:7]})
    mau = len({e[0] for e in ORACLE_DAILY_USAGE.keys() if e[1] in last_30})
    return _ok(
        {
            "dau": dau,
            "wau": wau,
            "mau": mau,
            "top_features": ["chart", "cosmic_weather", "oracle"],
            "oracle_funnel": {
                "sent": len([e for e in TELEMETRY_EVENTS if e["event_name"] == "oracle_send"]),
                "success": len([e for e in TELEMETRY_EVENTS if e["event_name"] == "oracle_success"]),
                "fail": len([e for e in TELEMETRY_EVENTS if e["event_name"] == "oracle_fail"]),
            },
            "bugs": BUG_REPORTS,
        }
    )


@router.post("/v1/dev/login-as")
async def dev_login_as(email: str):
    if os.getenv("APP_ENV", "development") not in {"development", "staging"}:
        _err("DEV_ONLY_ENDPOINT", "Endpoint disponível apenas em desenvolvimento/staging.", status_code=403)

    role = resolve_role(email)
    return _ok({"user_id": email, "role": role, "token_hint": "Use API_KEY atual com X-User-Id do usuário."})
