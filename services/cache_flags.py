import os

def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

CACHE_NATAL_ENABLED = _env_flag("CACHE_NATAL_ENABLED", default=False)
CACHE_SOLAR_RETURN_ENABLED = _env_flag("CACHE_SOLAR_RETURN_ENABLED", default=False)
CACHE_EPHEMERIS_ENABLED = _env_flag("CACHE_EPHEMERIS_ENABLED", default=False)
