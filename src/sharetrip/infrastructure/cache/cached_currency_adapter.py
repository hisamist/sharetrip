from datetime import date

from sharetrip.domain.interfaces.currency_port import CurrencyPort
from sharetrip.infrastructure.cache.redis_port import RedisPort

_TTL_SECONDS = 86_400  # 24h — un taux de change est stable sur une journée


def _cache_key(from_currency: str, to_currency: str, today: date) -> str:
    return f"rate:{from_currency}:{to_currency}:{today.isoformat()}"


class CachedCurrencyAdapter(CurrencyPort):
    """Decorator sur CurrencyPort — met en cache le taux de change par jour.

    Logique :
      1. Redis GET "rate:JPY:EUR:2026-04-10" → hit → retourne float
      2. miss → délègue à l'adapter interne → Redis SET (TTL 24h) → retourne float

    Clé incluant la date → même jour = même taux, lendemain = nouveau taux.
    """

    def __init__(self, inner: CurrencyPort, redis: RedisPort) -> None:
        self._inner = inner
        self._redis = redis

    def get_rate(self, from_currency: str, to_currency: str) -> float:
        if from_currency == to_currency:
            return 1.0

        key = _cache_key(from_currency, to_currency, date.today())

        cached = self._redis.get(key)
        if cached is not None:
            return float(cached)

        rate = self._inner.get_rate(from_currency, to_currency)
        self._redis.set(key, str(rate), ex=_TTL_SECONDS)
        return rate
