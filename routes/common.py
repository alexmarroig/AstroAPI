from __future__ import annotations
from typing import Optional
from fastapi import Header, Request
from core.security import require_api_key_and_user

def get_auth(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None),
):
    """Dependência para autenticação via API Key e User ID."""
    auth = require_api_key_and_user(
        authorization=authorization,
        x_user_id=x_user_id,
        request_path=request.url.path,
    )
    return auth
