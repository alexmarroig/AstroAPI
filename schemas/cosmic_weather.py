from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from .transits import TransitEvent

class CosmicWeatherResponse(BaseModel):
    """Resposta para o clima cósmico do dia."""
    date: str
    moon_phase: str
    moon_sign: str
    moon_sign_pt: Optional[str] = None
    deg_in_sign: Optional[float] = None
    headline: str
    text: str
    moon_phase_ptbr: Optional[str] = None
    moon_sign_ptbr: Optional[str] = None
    headline_ptbr: Optional[str] = None
    text_ptbr: Optional[str] = None
    resumo_ptbr: Optional[str] = None
    moon_ptbr: Optional[Dict[str, Any]] = None
    top_event: Optional[TransitEvent] = None
    trigger_event: Optional[TransitEvent] = None
    secondary_events: Optional[List[TransitEvent]] = None
    summary: Optional[Dict[str, str]] = None
    metadados_tecnicos: Optional[Dict[str, Any]] = None

class CosmicWeatherRangeResponse(BaseModel):
    """Resposta para um intervalo de clima cósmico."""
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    items: List[CosmicWeatherResponse]
    items_ptbr: Optional[List[Dict[str, Any]]] = None
