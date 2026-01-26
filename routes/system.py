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
