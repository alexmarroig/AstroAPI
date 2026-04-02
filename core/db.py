import logging
import os
import re
from typing import Optional

try:
    import asyncpg
except Exception:  # pragma: no cover
    asyncpg = None  # type: ignore

logger = logging.getLogger(__name__)
_pool: Optional["asyncpg.Pool"] = None

def _mask_dsn(dsn: str | None) -> str | None:
    if not dsn:
        return None
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", dsn)

def _resolve_db_url() -> str | None:
    return (
        os.getenv("DATABASE_URL")
        or os.getenv("SUPABASE_DB_URL")
        or os.getenv("SUPABASE_DB_CONNECTION_STRING")
    )

async def get_pool() -> "asyncpg.Pool":
    global _pool

    if _pool is not None:
        return _pool

    if asyncpg is None:
        raise RuntimeError("asyncpg not installed")

    db_url = _resolve_db_url()
    if not db_url:
        raise RuntimeError("DATABASE_URL not configured")

    _pool = await asyncpg.create_pool(
        dsn=db_url,
        min_size=1,
        max_size=5,
        command_timeout=60,
        statement_cache_size=0,
    )
    logger.info("db_pool_ready")
    return _pool

async def get_pool_or_none() -> Optional["asyncpg.Pool"]:
    try:
        return await get_pool()
    except Exception as exc:
        masked_dsn = _mask_dsn(_resolve_db_url())
        logger.exception(
            "db_pool_unavailable",
            extra={
                "error": str(exc),
                "error_type": type(exc).__name__,
                "dsn": masked_dsn,
            },
        )
        return None
