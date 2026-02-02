from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from services.time_utils import build_time_metadata

router = APIRouter()

def get_git_commit_hash() -> Optional[str]:
    """Obtém o hash do commit git atual."""
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent.parent)
            .decode()
            .strip()
        )
    except Exception:
        return None

ROADMAP_FEATURES = {
    "notifications": {"status": "beta", "notes": "feed diário via API; push aguardando provedor"},
    "mercury_retrograde_alert": {
        "status": "beta",
        "notes": "alertas sistêmicos quando Mercúrio entrar/saír de retrogradação",
    },
    "life_cycles": {"status": "planned", "notes": "mapear ciclos de retorno e progressões"},
    "auto_timezone": {"status": "beta", "notes": "usa timezone IANA no payload ou resolver via endpoint"},
    "tests": {"status": "in_progress", "notes": "priorizar casos críticos de cálculo"},
}

@router.get("/")
async def root():
    """Endpoint raiz para verificações de uptime e probes do Render."""
    return {
        "ok": True,
        "service": "astroengine",
        "version": "1.1.1", # Poderia vir de um config central
        "commit": get_git_commit_hash(),
        "env": {"openai": bool(os.getenv("OPENAI_API_KEY")), "log_level": os.getenv("LOG_LEVEL", "INFO")},
    }

@router.get("/health")
async def health_check():
    """Endpoint simples de health check."""
    return {"ok": True}

@router.get("/v1/system/roadmap")
async def roadmap():
    """Visão rápida do andamento das próximas funcionalidades."""
    return {
        "features": ROADMAP_FEATURES,
        "metadados_tecnicos": {
            "idioma": "pt-BR",
            "fonte_traducao": "backend",
            **build_time_metadata(timezone_name=None, tz_offset_minutes=None, local_dt=None),
        },
    }

@router.get("/v1/system/endpoints")
async def system_endpoints():
    """Lista todos os endpoints disponíveis na API (apenas para ambiente de desenvolvimento)."""
    if os.getenv("ENABLE_ENDPOINTS_LIST") != "1":
        raise HTTPException(status_code=404, detail="Endpoint não disponível.")

    # Nota: O catálogo completo pode ser movido para um arquivo JSON ou similar
    return {
        "endpoints": [], # Simplificado para esta refatoração
        "metadados": {
            "version": "v1",
            "ambiente": "dev",
            **build_time_metadata(timezone_name=None, tz_offset_minutes=None, local_dt=None),
        },
    }


@router.get("/api-test")
async def api_test():
    """Lista os principais endpoints disponíveis para integração rápida no frontend."""
    return {
        "ok": True,
        "mensagem": "Mapa de rotas disponíveis para o Inner Sky Guide.",
        "endpoints": [
            {"method": "GET", "path": "/api/daily-analysis/{date}"},
            {"method": "POST", "path": "/api/chat/astral-oracle"},
            {"method": "GET", "path": "/api/solar-return"},
            {"method": "GET", "path": "/api/lunar-calendar"},
            {"method": "GET", "path": "/api/secondary-progressions"},
            {"method": "POST", "path": "/v1/chart/natal"},
            {"method": "POST", "path": "/v1/chart/transits"},
            {"method": "POST", "path": "/v1/chart/render-data"},
            {"method": "POST", "path": "/v1/chart/distributions"},
            {"method": "POST", "path": "/v1/interpretation/natal"},
            {"method": "POST", "path": "/v1/transits/events"},
            {"method": "GET", "path": "/v1/transits/next-days"},
            {"method": "GET", "path": "/v1/transits/personal-today"},
            {"method": "POST", "path": "/v1/transits/live"},
            {"method": "GET", "path": "/v1/daily/summary"},
            {"method": "GET", "path": "/v1/cosmic-weather"},
            {"method": "GET", "path": "/v1/cosmic-weather/range"},
            {"method": "GET", "path": "/v1/moon/timeline"},
            {"method": "POST", "path": "/v1/solar-return/calculate"},
            {"method": "POST", "path": "/v1/solar-return/overlay"},
            {"method": "POST", "path": "/v1/solar-return/timeline"},
            {"method": "POST", "path": "/v1/ai/cosmic-chat"},
            {"method": "POST", "path": "/v1/diagnostics/ephemeris-check"},
            {"method": "GET", "path": "/v1/alerts/system"},
            {"method": "GET", "path": "/v1/alerts/retrogrades"},
            {"method": "GET", "path": "/v1/notifications/daily"},
            {"method": "POST", "path": "/v1/lunations/calculate"},
            {"method": "POST", "path": "/v1/progressions/secondary/calculate"},
            {"method": "POST", "path": "/v1/synastry/compare"},
        ],
        "metadados_tecnicos": build_time_metadata(
            timezone_name=None, tz_offset_minutes=None, local_dt=None
        ),
    }
