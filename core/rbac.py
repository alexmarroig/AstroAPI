from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RoleContext:
    user_id: str
    role: str


def resolve_role(user_id: str) -> str:
    admins = {x.strip() for x in os.getenv("ADMIN_USER_IDS", "admin@local,admin").split(",") if x.strip()}
    premium = {x.strip() for x in os.getenv("PREMIUM_USER_IDS", "premium@local,premium").split(",") if x.strip()}
    free = {x.strip() for x in os.getenv("FREE_USER_IDS", "free@local,free").split(",") if x.strip()}

    if user_id in admins:
        return "admin"
    if user_id in premium:
        return "premium"
    if user_id in free:
        return "free"
    return "free"


def entitlements_for_role(role: str) -> dict[str, bool]:
    premium_unlocked = role in {"premium", "admin"}
    return {
        "cosmic_weather_30d": premium_unlocked,
        "advanced_transits": premium_unlocked,
        "oracle_unlimited": premium_unlocked,
        "biwheel": premium_unlocked,
        "admin_dashboard": role == "admin",
    }
