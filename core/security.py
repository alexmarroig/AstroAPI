import base64
import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from fastapi import Header, HTTPException
from core.plans import get_user_plan
from core.limits import check_and_inc

logger = logging.getLogger(__name__)

def _parse_ts(ts: str) -> datetime | None:
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except ValueError:
        return None

def _b64url_decode(value: str) -> bytes | None:
    try:
        padded = value.replace("-", "+").replace("_", "/")
        padded += "=" * ((4 - len(padded) % 4) % 4)
        return base64.b64decode(padded)
    except Exception:
        return None

def verify_signature(
    user_id: str,
    ts: str,
    signature_b64url: str,
    secret: str,
    max_skew_seconds: int = 300,
) -> bool:
    ts_dt = _parse_ts(ts)
    if ts_dt is None:
        logger.warning("signature_ts_invalid", extra={"ts": ts})
        return False

    now = datetime.now(timezone.utc)
    ts_dt = ts_dt.astimezone(timezone.utc)
    skew = abs((now - ts_dt).total_seconds())
    if skew > max_skew_seconds:
        logger.warning("signature_skew_exceeded", extra={"skew_seconds": skew})
        return False

    msg = f"{user_id}:{ts}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    provided = _b64url_decode(signature_b64url)
    if provided is None:
        logger.warning("signature_decode_failed")
        return False

    return hmac.compare_digest(expected, provided)

def require_api_key_and_user(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    x_signature: str | None = Header(default=None),
    x_signature_ts: str | None = Header(default=None),
    request_path: str | None = None,
):
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="API_KEY nao configurada no servidor.")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization invalido. Use Bearer <API_KEY>.")

    token = authorization.split(" ", 1)[1].strip()
    if token != api_key:
        raise HTTPException(status_code=401, detail="API_KEY invalida.")

    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id ausente ou invalido.")

    sig_secret = os.getenv("PROXY_SHARED_SECRET")
    if sig_secret:
        if not x_signature or not x_signature_ts:
            raise HTTPException(status_code=401, detail="Assinatura ausente.")
        if not verify_signature(x_user_id, x_signature_ts, x_signature, sig_secret):
            raise HTTPException(status_code=401, detail="Assinatura invalida.")

    plan_obj = get_user_plan(x_user_id)
    endpoint = request_path or ""
    ok, msg = check_and_inc(x_user_id, endpoint, plan_obj.plan)
    if not ok:
        raise HTTPException(status_code=429, detail=msg)

    return {"user_id": x_user_id, "plan": plan_obj.plan}
