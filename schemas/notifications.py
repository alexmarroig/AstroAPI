from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class NotificationsDailyResponse(BaseModel):
    """Resposta para notificações diárias."""
    date: str
    items: List[Dict[str, Any]]
    items_ptbr: Optional[List[Dict[str, Any]]] = None
