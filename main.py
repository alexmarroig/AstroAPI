import os
import time
import uuid
import json
import logging
from datetime import datetime
from typing import Optional, Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from openai import OpenAI

from astro.ephemeris import compute_chart, compute_transits, compute_moon_only
from astro.aspects import compute_transit_aspects
from ai.prompts import build_cosmic_chat_messages

from core.security import require_api_key_and_user
from core.cache import cache
from core.plans import is_trial_or_premium

# -----------------------------
# Load env
# -----------------------------
load_dotenv()

# -----------------------------
# Logging (structured-ish)
# -----------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("astro-api")
logger.setLevel(LOG_LEVEL)
handler = logging.StreamHandler()
handler.setLevel(LOG_LEVEL)

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "ts": datetime.utcnow().isoformat() + "Z",
            "msg": record.getMessage(),
        }
        # extras
        for k in ("request_id", "path", "status", "latency_ms", "user_id"):
            if hasattr(record, k):
                payload[k] = getattr(record, k)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

handler.setFormatter(JsonFormatter())
logger.handlers = [handler]

# -----------------------------
# App
# -----------------------------
app = FastAPI(
    title="Premium Astrology API",
    description="Accurate astrological calculations using Swiss Ephemeris with AI-powered cosmic insights",
    version="1.1.0"
)

# -----------------------------
# CORS
# -----------------------------
origins = os.getenv("ALLOWED_ORIGINS", "*")
allowed = [o.strip() for o in origins.split(",")] if origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # Authorization + X-User-Id
)

# -----------------------------
# Middleware: request_id + logging
# -----------------------------
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    start = time.time()

    # attach to request state
    request.state.request_id = request_id

    try:
        response = await call_next(request)
        latency_ms = int((time.time() - start) * 1000)

        # don't log secrets; only safe fields
        extra = {
            "request_id": request_id,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": latency_ms,
        }
        logger.info("request", extra=type("obj", (), extra)())

        response.headers["X-Request-Id"] = request_id
        return response

    except Exception:
        latency_ms = int((time.time() - start) * 1000)
        extra = {
            "request_id": request_id,
            "path": request.url.path,
            "status": 500,
            "latency_ms": latency_ms,
        }
        logger.error("unhandled_exception", exc_info=True, extra=type("obj", (), extra)())
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro interno no servidor.", "request_id": request_id},
        )

# -----------------------------
# Exception handler: HTTPException
# -----------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    extra = {
        "request_id": request_id,
        "path": request.url.path,
        "status": exc.status_code,
        "latency_ms": None,
    }
    logger.warning("http_exception", extra=type("obj", (), extra)())
    payload = {"detail": exc.detail}
    if request_id:
        payload["request_id"] = request_id
    return JSONResponse(status_code=exc.status_code, content=payload)

# -----------------------------
# Auth dependency
# -----------------------------
def get_auth(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None),
):
    # require_api_key_and_user already does plan+rate-limit
    auth = require_api_key_and_user(
        authorization=authorization,
        x_user_id=x_user_id,
        request_path=request.url.path
    )
    return auth

# -----------------------------
# Models
# -----------------------------
class NatalChartRequest(BaseModel):
    year: int = Field(..., ge=1800, le=2100)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(0, ge=0, le=59)
    second: int = Field(0, ge=0, le=59)
    lat: float = Field(..., ge=-89.9999, le=89.9999)
    lng: float = Field(..., ge=-180, le=180)
    tz_offset_minutes: int = Field(0, ge=-840, le=840)
    house_system: str = Field("P", min_length=1, max_length=1)

class TransitsRequest(BaseModel):
    natal_year: int = Field(..., ge=1800, le=2100)
    natal_month: int = Field(..., ge=1, le=12)
    natal_day: int = Field(..., ge=1, le=31)
    natal_hour: int = Field(..., ge=0, le=23)
    natal_minute: int = Field(0, ge=0, le=59)
    natal_second: int = Field(0, ge=0, le=59)
    lat: float = Field(..., ge=-89.9999, le=89.9999)
    lng: float = Field(..., ge=-180, le=180)
    tz_offset_minutes: int = Field(0, ge=-840, le=840)
    target_date: str = Field(..., description="YYYY-MM-DD")

class CosmicChatRequest(BaseModel):
    user_question: str = Field(..., min_length=1)
    astro_payload: Dict[str, Any] = Field(...)
    tone: Optional[str] = None
    language: str = Field("pt-BR")

class CosmicWeatherResponse(BaseModel):
    date: str
    moon_phase: str
    moon_sign: str
    headline: str
    text: str

class RenderDataRequest(BaseModel):
    year: int
    month: int
    day: int
    hour: int
    minute: int = 0
    second: int = 0
    lat: float = Field(..., ge=-89.9999, le=89.9999)
    lng: float = Field(..., ge=-180, le=180)
    tz_offset_minutes: int = Field(0, ge=-840, le=840)
    house_system: str = "P"

# -----------------------------
# Helpers
# -----------------------------
def _parse_date_yyyy_mm_dd(s: str) -> tuple[int, int, int]:
    try:
        y, m, d = s.split("-")
        return int(y), int(m), int(d)
    except Exception:
        raise HTTPException(status_code=400, detail="Formato inválido de data. Use YYYY-MM-DD.")

def _moon_phase_4(phase_angle_deg: float) -> str:
    a = phase_angle_deg % 360
    if a < 45 or a >= 315:
        return "Nova"
    if 45 <= a < 135:
        return "Crescente"
    if 135 <= a < 225:
        return "Cheia"
    return "Minguante"

def _cw_text(phase: str, sign: str) -> str:
    options = [
        "O dia tende a favorecer mais presença emocional e escolhas com calma. Ajustes pequenos podem ter efeito grande.",
        "Pode ser um dia de observação interna. Priorize o essencial e evite decidir no pico da emoção.",
        "A energia pode ficar mais intensa em alguns momentos. Pausas curtas e ritmo consistente ajudam.",
    ]
    return options[hash(phase + sign) % len(options)]

def _now_yyyy_mm_dd() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")

# -----------------------------
# Routes
# -----------------------------
@app.get("/health")
async def health_check():
    return {"ok": True}

@app.post("/v1/chart/natal")
async def natal(body: NatalChartRequest, auth=Depends(get_auth)):
    try:
        cache_key = f"natal:{auth['user_id']}:{hash(body.model_dump_json())}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        chart = compute_chart(
            year=body.year,
            month=body.month,
            day=body.day,
            hour=body.hour,
            minute=body.minute,
            second=body.second,
            lat=body.lat,
            lng=body.lng,
            tz_offset_minutes=body.tz_offset_minutes,
            house_system=body.house_system
        )

        cache.set(cache_key, chart, ttl_seconds=30 * 24 * 3600)
        return chart
    except Exception as e:
        logger.error("natal_error", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao calcular mapa natal: {str(e)}")

@app.post("/v1/chart/transits")
async def transits(body: TransitsRequest, auth=Depends(get_auth)):
    y, m, d = _parse_date_yyyy_mm_dd(body.target_date)

    try:
        cache_key = f"transits:{auth['user_id']}:{body.target_date}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        natal_chart = compute_chart(
            year=body.natal_year,
            month=body.natal_month,
            day=body.natal_day,
            hour=body.natal_hour,
            minute=body.natal_minute,
            second=body.natal_second,
            lat=body.lat,
            lng=body.lng,
            tz_offset_minutes=body.tz_offset_minutes,
            house_system="P"
        )

        transit_chart = compute_transits(
            target_year=y,
            target_month=m,
            target_day=d,
            lat=body.lat,
            lng=body.lng,
            tz_offset_minutes=body.tz_offset_minutes
        )

        aspects = compute_transit_aspects(
            transit_planets=transit_chart["planets"],
            natal_planets=natal_chart["planets"]
        )

        # Cosmic Weather embutido
        moon = compute_moon_only(body.target_date)
        phase = _moon_phase_4(moon["phase_angle_deg"])
        sign = moon["moon_sign"]

        response = {
            "date": body.target_date,
            "cosmic_weather": {
                "moon_phase": phase,
                "moon_sign": sign,
                "headline": f"Lua {phase} em {sign}",
                "text": _cw_text(phase, sign),
            },
            "natal": natal_chart,
            "transits": transit_chart,
            "aspects": aspects,
        }

        cache.set(cache_key, response, ttl_seconds=6 * 3600)
        return response

    except Exception as e:
        logger.error("transits_error", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao calcular trânsitos: {str(e)}")

@app.get("/v1/cosmic-weather", response_model=CosmicWeatherResponse)
async def cosmic_weather(date: Optional[str] = None, auth=Depends(get_auth)):
    d = date or _now_yyyy_mm_dd()
    cache_key = f"cw:{auth['user_id']}:{d}"

    cached = cache.get(cache_key)
    if cached:
        return cached

    moon = compute_moon_only(d)
    phase = _moon_phase_4(moon["phase_angle_deg"])
    sign = moon["moon_sign"]

    payload = CosmicWeatherResponse(
        date=d,
        moon_phase=phase,
        moon_sign=sign,
        headline=f"Lua {phase} em {sign}",
        text=_cw_text(phase, sign),
    )

    cache.set(cache_key, payload.model_dump(), ttl_seconds=6 * 3600)
    return payload

@app.post("/v1/chart/render-data")
async def render_data(body: RenderDataRequest, auth=Depends(get_auth)):
    cache_key = f"render:{auth['user_id']}:{hash(body.model_dump_json())}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    natal = compute_chart(
        year=body.year,
        month=body.month,
        day=body.day,
        hour=body.hour,
        minute=body.minute,
        second=body.second,
        lat=body.lat,
        lng=body.lng,
        tz_offset_minutes=body.tz_offset_minutes,
        house_system=body.house_system
    )

    cusps = natal.get("houses", {}).get("cusps")
    if not cusps or len(cusps) < 12:
        raise HTTPException(status_code=500, detail="Cálculo não retornou houses.cusps (12 valores).")

    houses = []
    for i in range(12):
        start = float(cusps[i])
        end = float(cusps[(i + 1) % 12])
        if end < start:
            end += 360.0
        houses.append({"house": i + 1, "start_deg": start, "end_deg": end})

    planets = []
    for p in natal.get("planets", []):
        planets.append({
            "name": p.get("name"),
            "sign": p.get("sign"),
            "deg_in_sign": p.get("deg_in_sign"),
            "house": p.get("house"),
            "angle_deg": p.get("lon"),
        })

    resp = {
        "zodiac": ["Áries","Touro","Gêmeos","Câncer","Leão","Virgem","Libra","Escorpião","Sagitário","Capricórnio","Aquário","Peixes"],
        "houses": houses,
        "planets": planets,
        "premium_aspects": [] if is_trial_or_premium(auth["plan"]) else None
    }

    cache.set(cache_key, resp, ttl_seconds=30 * 24 * 3600)
    return resp

@app.post("/v1/ai/cosmic-chat")
async def cosmic_chat(body: CosmicChatRequest, auth=Depends(get_auth)):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY não configurada no servidor.")

    # Força pt-BR sempre (produto)
    language = "pt-BR"
    tone = body.tone or "calmo, adulto, tecnológico"

    try:
        client = OpenAI(api_key=api_key)

        messages = build_cosmic_chat_messages(
            user_question=body.user_question,
            astro_payload=body.astro_payload,
            tone=tone,
            language=language
        )

        max_tokens = 600 if auth["plan"] == "free" else 1100

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7
        )

        return {
            "response": response.choices[0].message.content,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }

    except Exception as e:
        logger.error("cosmic_chat_error", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro no processamento de IA: {str(e)}")
