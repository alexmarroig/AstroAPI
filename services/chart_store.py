import logging
from typing import Any

from core.db import get_pool_or_none

logger = logging.getLogger(__name__)

async def get_user_chart_payload(
    *,
    user_id: str,
    chart_type: str,
    period: str | None,
    engine_version: str,
    input_hash: str,
) -> dict[str, Any] | None:
    pool = await get_pool_or_none()
    if pool is None:
        return None

    query = """
        SELECT cc.payload_json
        FROM public.user_charts uc
        JOIN public.computed_charts cc ON cc.id = uc.computed_chart_id
        WHERE uc.user_id = $1
          AND uc.chart_type = $2
          AND uc.period IS NOT DISTINCT FROM $3
          AND uc.engine_version = $4
          AND uc.input_hash = $5
        LIMIT 1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, user_id, chart_type, period, engine_version, input_hash)
    return dict(row["payload_json"]) if row else None

async def get_computed_chart_payload(
    *,
    chart_type: str,
    engine_version: str,
    input_hash: str,
) -> tuple[str, dict[str, Any]] | None:
    pool = await get_pool_or_none()
    if pool is None:
        return None

    query = """
        SELECT id, payload_json
        FROM public.computed_charts
        WHERE chart_type = $1
          AND engine_version = $2
          AND input_hash = $3
        LIMIT 1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, chart_type, engine_version, input_hash)
    if not row:
        return None
    return str(row["id"]), dict(row["payload_json"])

async def upsert_computed_chart(
    *,
    chart_type: str,
    engine_version: str,
    input_hash: str,
    payload_json: dict[str, Any],
) -> str:
    pool = await get_pool_or_none()
    if pool is None:
        raise RuntimeError("db_unavailable")

    query = """
        INSERT INTO public.computed_charts
          (chart_type, engine_version, input_hash, payload_json)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (chart_type, engine_version, input_hash)
        DO UPDATE SET payload_json = EXCLUDED.payload_json, updated_at = now()
        RETURNING id
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, chart_type, engine_version, input_hash, payload_json)
    return str(row["id"])

async def upsert_user_chart(
    *,
    user_id: str,
    chart_type: str,
    period: str | None,
    engine_version: str,
    input_hash: str,
    computed_chart_id: str,
) -> None:
    pool = await get_pool_or_none()
    if pool is None:
        raise RuntimeError("db_unavailable")

    if period is None:
        query = """
            INSERT INTO public.user_charts
              (user_id, chart_type, period, engine_version, input_hash, computed_chart_id)
            VALUES ($1, $2, NULL, $3, $4, $5)
            ON CONFLICT (user_id, chart_type, engine_version, input_hash)
            WHERE period IS NULL
            DO UPDATE SET computed_chart_id = EXCLUDED.computed_chart_id, updated_at = now()
        """
        params = (user_id, chart_type, engine_version, input_hash, computed_chart_id)
    else:
        query = """
            INSERT INTO public.user_charts
              (user_id, chart_type, period, engine_version, input_hash, computed_chart_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (user_id, chart_type, period, engine_version, input_hash)
            DO UPDATE SET computed_chart_id = EXCLUDED.computed_chart_id, updated_at = now()
        """
        params = (user_id, chart_type, period, engine_version, input_hash, computed_chart_id)

    async with pool.acquire() as conn:
        await conn.execute(query, *params)

async def attach_user_chart(
    *,
    user_id: str,
    chart_type: str,
    period: str | None,
    engine_version: str,
    input_hash: str,
    computed_chart_id: str,
) -> None:
    try:
        await upsert_user_chart(
            user_id=user_id,
            chart_type=chart_type,
            period=period,
            engine_version=engine_version,
            input_hash=input_hash,
            computed_chart_id=computed_chart_id,
        )
    except Exception as exc:
        logger.warning("user_chart_upsert_failed", extra={"error": str(exc)})
