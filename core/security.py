import os
from fastapi import Header, HTTPException
from core.plans import get_user_plan
from core.limits import check_and_inc

def require_api_key_and_user(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    request_path: str | None = None,
):
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="API_KEY não configurada no servidor.")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization inválido. Use Bearer <API_KEY>.")

    token = authorization.split(" ", 1)[1].strip()
    if token != api_key:
        raise HTTPException(status_code=401, detail="API_KEY inválida.")

    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id ausente ou inválido.")

    plan_obj = get_user_plan(x_user_id)
    endpoint = request_path or ""
    ok, msg = check_and_inc(x_user_id, endpoint, plan_obj.plan)
    if not ok:
        raise HTTPException(status_code=429, detail=msg)

    return {"user_id": x_user_id, "plan": plan_obj.plan}
