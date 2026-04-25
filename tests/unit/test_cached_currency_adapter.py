from datetime import date

import pytest
from sharetrip.domain.interfaces.currency_port import CurrencyPort
from sharetrip.infrastructure.cache.cached_currency_adapter import (
    CachedCurrencyAdapter,
    _cache_key,
)

# ─── Stubs ────────────────────────────────────────────────────────────────────


class FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    def get(self, key: str) -> bytes | None:
        value = self._store.get(key)
        return value.encode() if isinstance(value, str) else value

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    def delete(self, *keys: str) -> None:
        for key in keys:
            self._store.pop(key, None)

    def has(self, key: str) -> bool:
        return key in self._store


class StubCurrencyPort(CurrencyPort):
    def __init__(self, rate: float = 0.0061):
        self._rate = rate
        self.call_count = 0

    def get_rate(self, from_currency: str, to_currency: str) -> float:
        self.call_count += 1
        return self._rate


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def inner() -> StubCurrencyPort:
    return StubCurrencyPort(rate=0.0061)


@pytest.fixture
def adapter(inner, fake_redis) -> CachedCurrencyAdapter:
    return CachedCurrencyAdapter(inner=inner, redis=fake_redis)


# ─── Cache miss ───────────────────────────────────────────────────────────────


class TestCacheMiss:
    def test_should_call_inner_adapter_when_cache_miss(self, adapter, inner):
        adapter.get_rate("JPY", "EUR")
        assert inner.call_count == 1

    def test_should_return_correct_rate_when_cache_miss(self, adapter):
        assert adapter.get_rate("JPY", "EUR") == pytest.approx(0.0061)

    def test_should_store_rate_in_redis_when_cache_miss(self, adapter, fake_redis):
        adapter.get_rate("JPY", "EUR")
        assert fake_redis.has(_cache_key("JPY", "EUR", date.today()))


# ─── Cache hit ────────────────────────────────────────────────────────────────


class TestCacheHit:
    def test_should_not_call_inner_adapter_when_cache_hit(self, adapter, inner):
        adapter.get_rate("JPY", "EUR")  # miss
        adapter.get_rate("JPY", "EUR")  # hit
        assert inner.call_count == 1

    def test_should_return_same_rate_when_cache_hit(self, adapter):
        first = adapter.get_rate("JPY", "EUR")
        second = adapter.get_rate("JPY", "EUR")
        assert first == pytest.approx(second)

    def test_should_read_from_redis_when_value_preloaded(self, inner, fake_redis):
        fake_redis.set(_cache_key("JPY", "EUR", date.today()), "0.0099")
        adapter = CachedCurrencyAdapter(inner=inner, redis=fake_redis)
        assert adapter.get_rate("JPY", "EUR") == pytest.approx(0.0099)
        assert inner.call_count == 0


# ─── Cas particuliers ─────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_should_return_one_without_redis_when_currencies_are_same(
        self, adapter, inner, fake_redis
    ):
        assert adapter.get_rate("EUR", "EUR") == 1.0
        assert inner.call_count == 0
        assert not fake_redis.has(_cache_key("EUR", "EUR", date.today()))

    def test_should_cache_each_pair_independently_when_different_currencies(self, adapter, inner):
        adapter.get_rate("JPY", "EUR")
        adapter.get_rate("USD", "EUR")
        assert inner.call_count == 2
        adapter.get_rate("JPY", "EUR")  # hit
        adapter.get_rate("USD", "EUR")  # hit
        assert inner.call_count == 2
