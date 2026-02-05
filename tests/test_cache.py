import threading

from core.cache import TTLCache


class FakeClock:
    def __init__(self, initial: float = 0.0):
        self._value = initial

    def now(self) -> float:
        return self._value

    def advance(self, seconds: float) -> None:
        self._value += seconds


def test_cache_expires_entries_lazily():
    clock = FakeClock()
    cache = TTLCache(sweep_interval_seconds=1000, time_func=clock.now)

    cache.set("k", "v", ttl_seconds=1)
    assert cache.get("k") == "v"

    clock.advance(2)
    assert cache.get("k") is None


def test_cache_sweep_removes_expired_entries():
    clock = FakeClock()
    cache = TTLCache(sweep_interval_seconds=2, time_func=clock.now)

    cache.set("expired", "x", ttl_seconds=1)
    cache.set("alive", "y", ttl_seconds=10)

    clock.advance(3)
    cache.set("new", "z", ttl_seconds=10)

    assert cache.get("expired") is None
    assert cache.get("alive") == "y"
    assert cache.get("new") == "z"


def test_cache_concurrent_get_set_is_thread_safe():
    cache = TTLCache()
    start = threading.Barrier(9)

    def writer(prefix: str):
        start.wait()
        for i in range(500):
            cache.set(f"{prefix}-{i}", i, ttl_seconds=30)

    def reader(prefix: str):
        start.wait()
        for i in range(500):
            value = cache.get(f"{prefix}-{i}")
            if value is not None:
                assert isinstance(value, int)

    threads = [
        threading.Thread(target=writer, args=("a",)),
        threading.Thread(target=writer, args=("b",)),
        threading.Thread(target=writer, args=("c",)),
        threading.Thread(target=writer, args=("d",)),
        threading.Thread(target=reader, args=("a",)),
        threading.Thread(target=reader, args=("b",)),
        threading.Thread(target=reader, args=("c",)),
        threading.Thread(target=reader, args=("d",)),
    ]

    for thread in threads:
        thread.start()

    start.wait()

    for thread in threads:
        thread.join()

    assert cache.get("a-499") == 499
    assert cache.get("d-499") == 499
