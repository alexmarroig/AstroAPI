import time
import os
from dataclasses import dataclass

TRIAL_SECONDS = 7 * 24 * 60 * 60

@dataclass
class UserPlan:
    user_id: str
    plan: str  # "free" | "trial" | "premium"
    trial_started_at: float

# memória (MVP). Depois a gente pluga em Supabase/DB.
_users: dict[str, UserPlan] = {}
_premium_users: set[str] = set()  # se quiser marcar premium manualmente


def _env_id_set(name: str) -> set[str]:
    raw = os.getenv(name, "")
    return {item.strip() for item in raw.split(",") if item.strip()}

def get_user_plan(user_id: str) -> UserPlan:
    now = time.time()
    admin_ids = _env_id_set("ADMIN_USER_IDS")
    premium_ids = _env_id_set("PREMIUM_USER_IDS")
    free_ids = _env_id_set("FREE_USER_IDS")
    environment = os.getenv("ENVIRONMENT", "development").lower()
    dev_mode = environment != "production"
    dev_auto_premium = os.getenv(
        "DEV_AUTO_PREMIUM",
        "true" if dev_mode else "false",
    ).lower() in {"1", "true", "yes", "on"}

    if user_id in _users:
        u = _users[user_id]
    else:
        u = UserPlan(user_id=user_id, plan="trial", trial_started_at=now)
        _users[user_id] = u

    # Em ambiente de desenvolvimento, permite desbloquear premium sem depender de seed externo.
    if dev_auto_premium:
        u.plan = "premium"
        return u

    # Overrides por ambiente (fonte de verdade operacional).
    if user_id in admin_ids or user_id in premium_ids:
        u.plan = "premium"
        return u

    if user_id in free_ids:
        u.plan = "free"
        return u

    if user_id in _premium_users:
        u.plan = "premium"
        return u

    # expira trial -> free
    if u.plan == "trial" and (now - u.trial_started_at) > TRIAL_SECONDS:
        u.plan = "free"

    return u

def is_trial_or_premium(plan: str) -> bool:
    return plan in ("trial", "premium")
