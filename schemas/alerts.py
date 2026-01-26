from __future__ import annotations
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

class SystemAlert(BaseModel):
    """Modelo para um alerta do sistema."""
    id: str
    severity: Literal["low", "medium", "high"]
    title: str
    body: str
    technical: Dict[str, Any] = Field(default_factory=dict)
    severity_ptbr: Optional[str] = None
    title_ptbr: Optional[str] = None
    body_ptbr: Optional[str] = None

class SystemAlertsResponse(BaseModel):
    """Resposta para a listagem de alertas do sistema."""
    date: str
    alerts: List[SystemAlert]
    alertas_ptbr: Optional[List[Dict[str, Any]]] = None
    tipos_ptbr: Optional[Dict[str, str]] = None
