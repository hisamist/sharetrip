from datetime import date

import pytest

from sharetrip.domain.interfaces.currency_port import CurrencyPort
from sharetrip.infrastructure.cache.cached_currency_adapter import (
    CachedCurrencyAdapter,
    _cache_key,
)


# ─── Stubs ────────────────────────────────────────────────────────────────────


class FakeRedis:
    """Redis en mémoire — aucun Docker requis."""

    def __init__(self):
        self._store: dict[str, bytes] = {}

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


# ─── Cache miss → appel interne ───────────────────────────────────────────────


class TestCacheMiss:
    def test_calls_inner_on_miss(self, adapter, inner):
        adapter.get_rate("JPY", "EUR")
        assert inner.call_count == 1

    def test_returns_correct_rate_on_miss(self, adapter):
        rate = adapter.get_rate("JPY", "EUR")
        assert rate == pytest.approx(0.0061)

    def test_stores_rate_in_redis(self, adapter, fake_redis):
        adapter.get_rate("JPY", "EUR")
        key = _cache_key("JPY", "EUR", date.today())
        assert fake_redis.has(key)


# ─── Cache hit → pas d'appel interne ─────────────────────────────────────────


class TestCacheHit:
    def test_does_not_call_inner_on_hit(self, adapter, inner):
        adapter.get_rate("JPY", "EUR")  # miss → stocké
        adapter.get_rate("JPY", "EUR")  # hit  → pas d'appel
        assert inner.call_count == 1

    def test_returns_cached_rate(self, adapter):
        first = adapter.get_rate("JPY", "EUR")
        second = adapter.get_rate("JPY", "EUR")
        assert first == pytest.approx(second)

    def test_hit_reads_from_redis_not_inner(self, inner, fake_redis):
        key = _cache_key("JPY", "EUR", date.today())
        fake_redis.set(key, "0.0099")  # valeur pré-chargée en cache

        adapter = CachedCurrencyAdapter(inner=inner, redis=fake_redis)
        rate = adapter.get_rate("JPY", "EUR")

        assert rate == pytest.approx(0.0099)
        assert inner.call_count == 0  # inner jamais appelé


# ─── Cas particuliers ─────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_same_currency_returns_one_without_redis(self, adapter, inner, fake_redis):
        rate = adapter.get_rate("EUR", "EUR")
        assert rate == 1.0
        assert inner.call_count == 0
        assert not fake_redis.has(_cache_key("EUR", "EUR", date.today()))

    def test_different_pairs_cached_independently(self, adapter, inner):
        adapter.get_rate("JPY", "EUR")
        adapter.get_rate("USD", "EUR")
        assert inner.call_count == 2

        adapter.get_rate("JPY", "EUR")  # hit
        adapter.get_rate("USD", "EUR")  # hit
        assert inner.call_count == 2  # toujours 2
