from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field

class EphemerisCheckRequest(BaseModel):
    """Modelo para requisição de diagnóstico de efemérides."""
    datetime_local: datetime = Field(..., description="Data/hora local, ex.: 2024-01-01T12:00:00")
    timezone: str = Field(..., description="Timezone IANA, ex.: Etc/UTC")
    lat: float = Field(..., ge=-89.9999, le=89.9999)
    lng: float = Field(..., ge=-180, le=180)
