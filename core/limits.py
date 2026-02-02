import time
from collections import defaultdict

# contador por (day_key, user_id, endpoint)
_counts = defaultdict(int)
_hour_counts = defaultdict(int)

def _day_key() -> str:
    t = time.gmtime()
    return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"

def _hour_key() -> str:
    t = time.gmtime()
    return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}-{t.tm_hour:02d}"

def check_and_inc(user_id: str, endpoint: str, plan: str) -> tuple[bool, str]:
    hour = _hour_key()
    hour_key = (hour, user_id)
    hourly_limit = 100
    if _hour_counts[hour_key] >= hourly_limit:
        return False, "Você alcançou o limite horário de 100 requisições. Respire e tente novamente em instantes."
    _hour_counts[hour_key] += 1

    day = _day_key()
    key = (day, user_id, endpoint)

    # limites (MVP). Ajuste como quiser:
    if plan == "free":
        limits = {
            "/v1/ai/cosmic-chat": 5,      # free bem limitado
            "/v1/chart/transits": 30,
            "/v1/cosmic-weather": 60,
            "/v1/chart/natal": 20,
            "/v1/chart/render-data": 60,
        }
    elif plan == "trial":
        limits = {
            "/v1/ai/cosmic-chat": 100,
            "/v1/chart/transits": 500,
            "/v1/cosmic-weather": 500,
            "/v1/chart/natal": 200,
            "/v1/chart/render-data": 500,
        }
    else:  # premium
        limits = {
            "/v1/ai/cosmic-chat": 1000,
            "/v1/chart/transits": 5000,
            "/v1/cosmic-weather": 5000,
            "/v1/chart/natal": 2000,
            "/v1/chart/render-data": 5000,
        }

    limit = limits.get(endpoint, 200 if plan != "free" else 50)
    used = _counts[key]

    if used >= limit:
        return False, f"Limite diário atingido para este recurso ({limit}/dia)."

    _counts[key] += 1
    return True, ""
