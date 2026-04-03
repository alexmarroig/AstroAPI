import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.errors import build_error
from routes import (
    account,
    ai,
    alerts,
    chart,
    checkin,
    cosmic_decision,
    cycles,
    cosmic_weather,
    diagnostics,
    forecast,
    i18n,
    inner_sky,
    insights,
    lunations,
    modular_engine,
    notifications,
    professional,
    progressions,
    solar_return,
    synastry,
    system,
    time as time_route,
    transits,
)
from services.observability import OperationalEvent, observability_orchestrator
from services.cache_flags import (
    CACHE_NATAL_ENABLED,
    CACHE_SOLAR_RETURN_ENABLED,
    CACHE_EPHEMERIS_ENABLED,
)
from core.db import get_pool_or_none

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("astro-api")
logger.setLevel(LOG_LEVEL)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "ts": datetime.utcnow().isoformat() + "Z",
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        standard = {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
        }
        for key, value in record.__dict__.items():
            if key in standard or key in payload:
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except TypeError:
                payload[key] = str(value)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.handlers = [handler]
logger.propagate = False


def _log(level: str, message: str, **extra: Any) -> None:
    getattr(logger, level)(message, extra=extra)


app = FastAPI(
    title="Premium Astrology API",
    description="API de Astrologia com arquitetura modular.",
    version="2.0.0",
)


@app.on_event("startup")
async def startup_event() -> None:
    ai.initialize_openai_client(app)
    if CACHE_NATAL_ENABLED or CACHE_SOLAR_RETURN_ENABLED or CACHE_EPHEMERIS_ENABLED:
        pool = await get_pool_or_none()
        if pool is None:
            _log(
                "warning",
                "db_pool_unavailable_startup",
                cache_enabled=True,
            )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await ai.shutdown_openai_client(app)


origins = os.getenv("ALLOWED_ORIGINS", "*")
allowed = [o.strip() for o in origins.split(",")] if origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-XSS-Protection", "0")
    response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    return response


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.time()

    try:
        response = await call_next(request)
        latency_ms = int((time.time() - start_time) * 1000)
        event = OperationalEvent(
            endpoint=request.url.path,
            latency_ms=latency_ms,
            request_id=request_id,
            user_plan=request.headers.get("X-User-Plan", "unknown"),
            status_code=response.status_code,
        )
        observability = observability_orchestrator.process_event(event)

        _log(
            "info",
            "request_processed",
            request_id=request_id,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
            endpoint=event.endpoint,
            user_plan=event.user_plan,
            observability_alert=observability["alert"],
        )

        response.headers["X-Request-Id"] = request_id
        return response
    except Exception as exc:
        latency_ms = int((time.time() - start_time) * 1000)
        _log(
            "error",
            "unhandled_exception",
            request_id=request_id,
            path=request.url.path,
            status=500,
            latency_ms=latency_ms,
            error=str(exc),
        )
        err = build_error(500, "Tente novamente em 1 minuto", retryable=True)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": err.to_response(), "request_id": request_id},
            headers={"X-Request-Id": request_id},
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    err = build_error(exc.status_code, str(exc.detail), retryable=exc.status_code >= 500)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "data": None,
            "error": err.to_response(),
            "detail": str(exc.detail),
            "request_id": request_id,
        },
        headers={"X-Request-Id": request_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    err = build_error(422, "Payload inválido.", retryable=False)
    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "data": None,
            "error": {**err.to_response(), "details": exc.errors()},
            "detail": exc.errors(),
            "request_id": request_id,
        },
        headers={"X-Request-Id": request_id},
    )


app.include_router(system.router, tags=["System"])
app.include_router(account.router, tags=["Account"])
app.include_router(time_route.router, tags=["Time"])
app.include_router(chart.router, tags=["Chart"])
app.include_router(checkin.router, tags=["Check-in"])
app.include_router(cycles.router, tags=["Cycles"])
app.include_router(cosmic_decision.router, tags=["Cosmic Decision"])
app.include_router(insights.router, tags=["Insights"])
app.include_router(transits.router, tags=["Transits"])
app.include_router(cosmic_weather.router, tags=["Cosmic Weather"])
app.include_router(solar_return.router, tags=["Solar Return"])
app.include_router(ai.router, tags=["AI"])
app.include_router(diagnostics.router, tags=["Diagnostics"])
app.include_router(alerts.router, tags=["Alerts"])
app.include_router(notifications.router, tags=["Notifications"])
app.include_router(lunations.router, tags=["Lunations"])
app.include_router(progressions.router, tags=["Progressions"])
app.include_router(modular_engine.router, tags=["Modular Engine"])
app.include_router(inner_sky.router, tags=["Inner Sky"])
app.include_router(i18n.router, tags=["I18N"])
app.include_router(professional.router, tags=["Professional"])
app.include_router(synastry.router, tags=["Synastry"])
app.include_router(forecast.router, tags=["Forecast"])
