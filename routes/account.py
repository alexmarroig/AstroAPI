from __future__ import annotations
import logging
import time
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from .common import get_auth
from core.plans import get_user_plan, TRIAL_SECONDS

router = APIRouter()
logger = logging.getLogger("astro-api")

@router.get("/v1/account/status")
async def account_status(request: Request, auth=Depends(get_auth)):
    """Retorna o status da conta e do plano do usuário."""
    user_id = auth.get("user_id")
    plan_obj = get_user_plan(user_id)

    trial_ends_at = None
    if plan_obj.plan == "trial":
        trial_ends_at = datetime.utcfromtimestamp(plan_obj.trial_started_at + TRIAL_SECONDS).isoformat() + "Z"

    features = {
        "can_see_full_daily_analysis": plan_obj.plan != "free",
        "can_see_next_30_days": plan_obj.plan != "free",
        "can_see_personal_transits": plan_obj.plan != "free",
        "can_create_multiple_sinastries": plan_obj.plan == "premium",
    }

    return {
        "plan": plan_obj.plan,
        "trial_ends_at": trial_ends_at,
        "renews_at": None,
        "features": features,
        "account": {
            "name": None,
            "birth_date": None,
            "birth_time": None,
            "birth_city": None,
            "timezone": None,
        },
        "metadados": {
            "requested_at": datetime.utcnow().isoformat() + "Z",
            "trial_started_at": datetime.utcfromtimestamp(plan_obj.trial_started_at).isoformat() + "Z",
        },
    }

@router.get("/v1/account/plan")
async def account_plan(auth=Depends(get_auth)):
    """Informa o plano atual e detalhes do trial."""
    plan_obj = get_user_plan(auth["user_id"])
    now = int(time.time())
    trial_ends_at = int(plan_obj.trial_started_at + TRIAL_SECONDS)
    trial_days_left = max(0, (trial_ends_at - now + 86399) // 86400) if plan_obj.plan == "trial" else 0
    return {
        "plan": plan_obj.plan,
        "trial_started_at": int(plan_obj.trial_started_at),
        "trial_ends_at": trial_ends_at,
        "trial_days_left": trial_days_left,
        "is_trial": plan_obj.plan == "trial",
    }


@router.post("/v1/account/plan-status")
async def account_plan_status(auth=Depends(get_auth)):
    """Compat endpoint para frontend (plan-status)."""
    plan_obj = get_user_plan(auth["user_id"])
    now = int(time.time())
    trial_ends_at = int(plan_obj.trial_started_at + TRIAL_SECONDS)
    trial_days_left = max(0, (trial_ends_at - now + 86399) // 86400) if plan_obj.plan == "trial" else 0

    features = {
        "daily_cards": plan_obj.plan != "free",
        "cosmic_chat": plan_obj.plan != "free",
        "synastry": plan_obj.plan == "premium",
        "solar_return": plan_obj.plan != "free",
        "progressions": plan_obj.plan != "free",
        "extended_timeline": plan_obj.plan != "free",
    }

    return {
        "plan": plan_obj.plan,
        "trial_ends_at": trial_ends_at if plan_obj.plan == "trial" else None,
        "trial_days_left": trial_days_left if plan_obj.plan == "trial" else 0,
        "features": features,
    }
