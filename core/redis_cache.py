from __future__ import annotations

import json
import os
from typing import Any, Optional

try:
    from redis.asyncio import Redis
except Exception:  # pragma: no cover
    Redis = None  # type: ignore


class RedisJSONCache:
    def __init__(self) -> None:
        self._client: Optional[Redis] = None
        self._enabled = False
        self._init_from_env()

    def _init_from_env(self) -> None:
        if Redis is None:
            return
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return
        self._client = Redis.from_url(redis_url, decode_responses=True)
        self._enabled = True

    async def get_json(self, key: str) -> Optional[Any]:
        if not self._enabled or self._client is None:
            return None
        raw = await self._client.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        if not self._enabled or self._client is None:
            return
        serialized = json.dumps(value, ensure_ascii=False)
        await self._client.setex(key, ttl_seconds, serialized)


redis_cache = RedisJSONCache()
