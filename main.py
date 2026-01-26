import os
import time
import uuid
import json
import logging
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# Importação dos roteadores modulares
from routes import (
    system, account, time as time_route, chart, insights, transits,
    cosmic_weather, solar_return, ai, diagnostics, alerts, notifications,
    lunations, progressions
)

# -----------------------------
# Carregamento de Configurações
# -----------------------------
load_dotenv()

# -----------------------------
# Logging Estruturado (JSON)
# -----------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("astro-api")
logger.setLevel(LOG_LEVEL)

class JsonFormatter(logging.Formatter):
    """Formatador de log para saída em JSON, facilitando o monitoramento em produção."""
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "ts": datetime.utcnow().isoformat() + "Z",
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        # Adiciona campos extras do record que não são padrão
        standard = {"args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName", "levelname",
                    "levelno", "lineno", "message", "module", "msecs", "msg", "name", "pathname", "process",
                    "processName", "relativeCreated", "stack_info", "thread", "threadName"}
        for key, value in record.__dict__.items():
            if key not in standard and key not in payload:
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
    """Wrapper para logging estruturado."""
    log_method = getattr(logger, level)
    log_method(message, extra=extra)

# Aliases para compatibilidade com testes legados
from services.time_utils import get_tz_offset_minutes as _tz_offset_for

# -----------------------------
# Inicialização do App FastAPI
# -----------------------------
app = FastAPI(
    title="Premium Astrology API",
    description="API de Astrologia de alta precisão usando Swiss Ephemeris e IA.",
    version="1.1.2", # Versão incrementada após refatoração
)

# -----------------------------
# Configuração de CORS
# -----------------------------
origins = os.getenv("ALLOWED_ORIGINS", "*")
allowed = [o.strip() for o in origins.split(",")] if origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Middleware de Logging e ID de Requisição
# -----------------------------
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.time()
    try:
        response = await call_next(request)
        latency_ms = int((time.time() - start_time) * 1000)

        _log("info", "request_processed",
             request_id=request_id, path=request.url.path,
             status=response.status_code, latency_ms=latency_ms)

        response.headers["X-Request-Id"] = request_id
        return response

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        _log("error", "unhandled_exception",
             request_id=request_id, path=request.url.path,
             status=500, latency_ms=latency_ms, error=str(e))

        return JSONResponse(
            status_code=500,
            content={
                "detail": "Erro interno no servidor.",
                "request_id": request_id,
                "code": "internal_error",
            },
            headers={"X-Request-Id": request_id},
        )

# -----------------------------
# Handlers de Exceção Globais
# -----------------------------
# Estes handlers garantem que a API responda sempre em um formato padrão,
# mesmo quando ocorrem erros inesperados ou validações falham.

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "request_id": request_id,
            "code": f"http_{exc.status_code}",
        },
        headers={"X-Request-Id": request_id},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Captura erros de validação do Pydantic (ex: campos faltando ou formato inválido)."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "request_id": request_id,
            "code": "validation_error",
        },
        headers={"X-Request-Id": request_id},
    )

# -----------------------------
# Inclusão de Rotas Modulares
# -----------------------------
# Cada módulo de rota foi isolado para facilitar a manutenção
app.include_router(system.router, tags=["System"])
app.include_router(account.router, tags=["Account"])
app.include_router(time_route.router, tags=["Time"])
app.include_router(chart.router, tags=["Chart"])
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
