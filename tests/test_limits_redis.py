from core.limits import RedisRateLimitStore


class FakePipeline:
    def __init__(self, db):
        self.db = db
        self.ops = []

    def incr(self, key):
        self.ops.append(("incr", key))
        return self

    def expire(self, key, ttl, nx=False):
        self.ops.append(("expire", key, ttl, nx))
        return self

    def execute(self):
        incr_key = [op[1] for op in self.ops if op[0] == "incr"][0]
        self.db[incr_key] = self.db.get(incr_key, 0) + 1
        incr_result = self.db[incr_key]
        return [incr_result, True]


class FakeRedisClient:
    def __init__(self):
        self.db = {}

    def pipeline(self):
        return FakePipeline(self.db)


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
