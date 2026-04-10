import redis as redis_lib
import jwt
from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from sharetrip.config import Settings, get_settings
from sharetrip.domain.entities.user import User
from sharetrip.infrastructure.adapters.currency_adapter import (
    FrankfurterCurrencyAdapter,
)
from sharetrip.infrastructure.auth.jwt_service import JWTService
from sharetrip.infrastructure.auth.password_service import PasswordService
from sharetrip.infrastructure.cache.cached_currency_adapter import CachedCurrencyAdapter
from sharetrip.infrastructure.cache.cached_trip_repository import CachedTripRepository
from sharetrip.infrastructure.db.sql_trip_repository import SQLTripRepository
from sharetrip.infrastructure.db.sql_user_repository import SQLUserRepository
from sharetrip.use_cases.login_user import LoginInput, LoginUseCase
from sharetrip.use_cases.register_user import RegisterInput, RegisterUseCase

app = FastAPI(
    title="ShareTrip API",
    description="Enterprise-grade settlement engine with Clean Architecture",
    version="0.1.0",
)

_bearer = HTTPBearer()


# ─── Dépendances ──────────────────────────────────────────────────────────────


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


# ─── Schemas HTTP ─────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    username: str
    display_name: str
    email: EmailStr
    password: str
    phone: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    email: str


# ─── Routes Auth ──────────────────────────────────────────────────────────────


@app.post("/auth/register", response_model=UserResponse, status_code=201, tags=["Auth"])
def register(
    body: RegisterRequest,
    session: Session = Depends(get_db_session),
):
    use_case = RegisterUseCase(
        user_repository=SQLUserRepository(session),
        password_service=PasswordService(),
    )
    try:
        user = use_case.execute(
            RegisterInput(
                username=body.username,
                display_name=body.display_name,
                email=body.email,
                password=body.password,
                phone=body.phone,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
    )


@app.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(
    body: LoginRequest,
    session: Session = Depends(get_db_session),
    jwt_service: JWTService = Depends(get_jwt_service),
):
    use_case = LoginUseCase(
        user_repository=SQLUserRepository(session),
        password_service=PasswordService(),
        jwt_service=jwt_service,
    )
    try:
        output = use_case.execute(LoginInput(email=body.email, password=body.password))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    return TokenResponse(access_token=output.access_token)


# ─── Route protégée (exemple) ─────────────────────────────────────────────────


@app.get("/auth/me", response_model=UserResponse, tags=["Auth"])
def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        display_name=current_user.display_name,
        email=current_user.email,
    )


# ─── Health ───────────────────────────────────────────────────────────────────


@app.get("/health", tags=["Monitoring"])
def health_check(settings: Settings = Depends(get_settings)):
    return {"status": "healthy", "version": "0.1.0", "env": settings.app_env}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
