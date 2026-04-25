import pytest


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset in-memory rate limit counters after each test for isolation."""
    yield
    from sharetrip.api.limiter import limiter

    limiter._storage.reset()
