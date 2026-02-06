from core.limits import RedisRateLimitStore


class FakeRedisClient:
    def __init__(self):
        self.db = {}

    def eval(self, script, keys, key, ttl):
        self.db[key] = self.db.get(key, 0) + 1
        return self.db[key]


def test_redis_store_uses_atomic_pipeline_and_window_key():
    client = FakeRedisClient()
    store = RedisRateLimitStore(client)

    count1 = store.incr_with_window(
        user_id="u1",
        endpoint="/v1/chart/natal",
        window="day:2026-01-20",
        ttl_seconds=123,
    )
    count2 = store.incr_with_window(
        user_id="u1",
        endpoint="/v1/chart/natal",
        window="day:2026-01-20",
        ttl_seconds=123,
    )

    key = "ratelimit:day:2026-01-20:u1:/v1/chart/natal"
    assert client.db[key] == 2
    assert count1 == 1
    assert count2 == 2
