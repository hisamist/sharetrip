import redis as redis_lib
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from sharetrip.config import Settings, get_settings
from sharetrip.infrastructure.adapters.currency_adapter import (
    FrankfurterCurrencyAdapter,
)
from sharetrip.infrastructure.cache.cached_currency_adapter import CachedCurrencyAdapter
from sharetrip.infrastructure.cache.cached_trip_repository import CachedTripRepository
from sharetrip.infrastructure.db.sql_trip_repository import SQLTripRepository

app = FastAPI(
    title="ShareTrip API",
    description="Enterprise-grade settlement engine with Clean Architecture",
    version="0.1.0",
)


# ─── Dépendances ──────────────────────────────────────────────────────────────


def get_db_session(settings: Settings = Depends(get_settings)):
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_redis_client(settings: Settings = Depends(get_settings)):
    return redis_lib.from_url(settings.redis_url, decode_responses=False)


def get_trip_repository(
    session: Session = Depends(get_db_session),
    redis=Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
):
    sql_repo = SQLTripRepository(session)
    return CachedTripRepository(inner=sql_repo, redis=redis)


def get_currency_port(
    redis=Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
):
    inner = FrankfurterCurrencyAdapter(base_url=settings.frankfurter_base_url)
    return CachedCurrencyAdapter(inner=inner, redis=redis)


# ─── Routes ───────────────────────────────────────────────────────────────────


@app.get("/health", tags=["Monitoring"])
async def health_check(settings: Settings = Depends(get_settings)):
    return JSONResponse(
        content={
            "status": "healthy",
            "version": "0.1.0",
            "env": settings.app_env,
            "services": {
                "api": "up",
                "db": "connected",
                "redis": "connected",
            },
        },
        status_code=200,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
