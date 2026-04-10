import jwt
import redis as redis_lib
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from sharetrip.config import Settings, get_settings
from sharetrip.domain.entities.user import User
from sharetrip.infrastructure.adapters.currency_adapter import (
    FrankfurterCurrencyAdapter,
)
from sharetrip.infrastructure.auth.jwt_service import JWTService
from sharetrip.infrastructure.cache.cached_currency_adapter import CachedCurrencyAdapter
from sharetrip.infrastructure.cache.cached_trip_repository import CachedTripRepository
from sharetrip.infrastructure.db.sql_trip_repository import SQLTripRepository
from sharetrip.infrastructure.db.sql_user_repository import SQLUserRepository

_bearer = HTTPBearer()


def get_db_session(settings: Settings = Depends(get_settings)):
    engine = create_engine(settings.database_url)
    session = sessionmaker(bind=engine)()
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
):
    return CachedTripRepository(inner=SQLTripRepository(session), redis=redis)


def get_currency_port(
    redis=Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
):
    return CachedCurrencyAdapter(
        inner=FrankfurterCurrencyAdapter(base_url=settings.frankfurter_base_url),
        redis=redis,
    )


def get_jwt_service(settings: Settings = Depends(get_settings)) -> JWTService:
    return JWTService(secret_key=settings.jwt_secret_key)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> User:
    """Extrait et valide le JWT — injecte l'utilisateur courant."""
    try:
        payload = JWTService(settings.jwt_secret_key).decode_token(
            credentials.credentials
        )
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    user = SQLUserRepository(session).get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user
