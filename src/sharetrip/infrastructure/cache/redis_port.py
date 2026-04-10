from typing import Protocol


class RedisPort(Protocol):
    """Protocol minimal pour interagir avec Redis.

    - Production : redis.Redis (via Docker)
    - Tests      : FakeRedis (dict Python, aucun Docker requis)

    Seules les méthodes utilisées dans le projet sont déclarées ici.
    """

    def get(self, key: str) -> bytes | None: ...

    def set(self, key: str, value: str, ex: int | None = None) -> None: ...

    def delete(self, *keys: str) -> None: ...
