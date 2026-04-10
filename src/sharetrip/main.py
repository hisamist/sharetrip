import redis as redis_lib
import jwt
from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from sharetrip.config import Settings, get_settings
from sharetrip.domain.entities.expense import ExpenseSplit, SplitType
from sharetrip.domain.entities.membership import Membership
from sharetrip.domain.entities.trip import Trip
from sharetrip.domain.entities.user import User
from sharetrip.domain.services.split_factory import SplitFactory
from sharetrip.infrastructure.adapters.currency_adapter import (
    FrankfurterCurrencyAdapter,
)
from sharetrip.infrastructure.auth.jwt_service import JWTService
from sharetrip.infrastructure.auth.password_service import PasswordService
from sharetrip.infrastructure.cache.cached_currency_adapter import CachedCurrencyAdapter
from sharetrip.infrastructure.cache.cached_trip_repository import CachedTripRepository
from sharetrip.infrastructure.db.sql_trip_repository import SQLTripRepository
from sharetrip.infrastructure.db.sql_user_repository import SQLUserRepository
from sharetrip.use_cases.add_expense import AddExpenseInput, AddExpenseUseCase
from sharetrip.use_cases.compute_settlements import (
    ComputeSettlementsInput,
    ComputeSettlementsUseCase,
)
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


# ─── Schemas Trips ────────────────────────────────────────────────────────────


class TripRequest(BaseModel):
    name: str
    base_currency: str


class TripResponse(BaseModel):
    id: int
    name: str
    base_currency: str


# ─── Schemas Expenses ─────────────────────────────────────────────────────────


class SplitRequest(BaseModel):
    user_id: int
    share_ratio: float


class AddExpenseRequest(BaseModel):
    title: str
    amount: float
    currency: str
    split_type: SplitType
    category: str | None = None
    splits: list[SplitRequest] = []


class SplitResponse(BaseModel):
    user_id: int
    amount_owed: float
    share_ratio: float


class ExpenseResponse(BaseModel):
    id: int
    trip_id: int
    paid_by: int
    title: str
    amount_pivot: float
    original_currency: str | None
    exchange_rate: float
    split_type: SplitType
    category: str | None
    splits: list[SplitResponse] = []


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


# ─── Routes Trips ─────────────────────────────────────────────────────────────


@app.post("/trips", response_model=TripResponse, status_code=201, tags=["Trips"])
def create_trip(
    body: TripRequest,
    trip_repo=Depends(get_trip_repository),
    current_user: User = Depends(get_current_user),
):
    trip = trip_repo.save_trip(Trip(name=body.name, base_currency=body.base_currency))
    trip_repo.add_member(Membership(trip_id=trip.id, user_id=current_user.id))
    return TripResponse(id=trip.id, name=trip.name, base_currency=trip.base_currency)


@app.get("/trips/{trip_id}", response_model=TripResponse, tags=["Trips"])
def get_trip(
    trip_id: int,
    trip_repo=Depends(get_trip_repository),
    _: User = Depends(get_current_user),
):
    trip = trip_repo.get_trip(trip_id)
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        )
    return TripResponse(id=trip.id, name=trip.name, base_currency=trip.base_currency)


@app.post("/trips/{trip_id}/members", status_code=204, tags=["Trips"])
def add_member(
    trip_id: int,
    user_id: int,
    trip_repo=Depends(get_trip_repository),
    _: User = Depends(get_current_user),
):
    trip = trip_repo.get_trip(trip_id)
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        )
    trip_repo.add_member(Membership(trip_id=trip_id, user_id=user_id))


# ─── Routes Expenses ──────────────────────────────────────────────────────────


def _to_expense_response(expense, splits) -> ExpenseResponse:
    return ExpenseResponse(
        id=expense.id,
        trip_id=expense.trip_id,
        paid_by=expense.paid_by,
        title=expense.title,
        amount_pivot=expense.amount_pivot,
        original_currency=expense.original_currency,
        exchange_rate=expense.exchange_rate,
        split_type=expense.split_type,
        category=expense.category,
        splits=[
            SplitResponse(
                user_id=s.user_id,
                amount_owed=s.amount_owed,
                share_ratio=s.share_ratio,
            )
            for s in splits
        ],
    )


@app.post(
    "/trips/{trip_id}/expenses",
    response_model=ExpenseResponse,
    status_code=201,
    tags=["Expenses"],
)
def add_expense(
    trip_id: int,
    body: AddExpenseRequest,
    trip_repo=Depends(get_trip_repository),
    currency_port=Depends(get_currency_port),
    current_user: User = Depends(get_current_user),
):
    splits = [
        ExpenseSplit(expense_id=None, user_id=s.user_id, share_ratio=s.share_ratio)
        for s in body.splits
    ]
    use_case = AddExpenseUseCase(
        trip_repository=trip_repo,
        currency_port=currency_port,
        split_factory=SplitFactory(),
    )
    try:
        output = use_case.execute(
            AddExpenseInput(
                trip_id=trip_id,
                paid_by=current_user.id,
                title=body.title,
                amount=body.amount,
                currency=body.currency,
                split_type=body.split_type,
                category=body.category,
                splits=splits,
            )
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )

    return _to_expense_response(output.expense, output.splits)


@app.get(
    "/trips/{trip_id}/expenses",
    response_model=list[ExpenseResponse],
    tags=["Expenses"],
)
def list_expenses(
    trip_id: int,
    trip_repo=Depends(get_trip_repository),
    _: User = Depends(get_current_user),
):
    trip = trip_repo.get_trip(trip_id)
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        )

    expenses = trip_repo.list_expenses(trip_id)
    return [
        _to_expense_response(expense, trip_repo.get_splits(expense.id))
        for expense in expenses
    ]


# ─── Routes Settlements ───────────────────────────────────────────────────────


class TransferResponse(BaseModel):
    from_user_id: int
    to_user_id: int
    amount: float


@app.get(
    "/trips/{trip_id}/settlements",
    response_model=list[TransferResponse],
    tags=["Settlements"],
)
def get_settlements(
    trip_id: int,
    trip_repo=Depends(get_trip_repository),
    _: User = Depends(get_current_user),
):
    try:
        output = ComputeSettlementsUseCase(trip_repo).execute(
            ComputeSettlementsInput(trip_id=trip_id)
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return [
        TransferResponse(
            from_user_id=t.from_user_id,
            to_user_id=t.to_user_id,
            amount=t.amount,
        )
        for t in output.transfers
    ]


# ─── Health ───────────────────────────────────────────────────────────────────


@app.get("/health", tags=["Monitoring"])
def health_check(settings: Settings = Depends(get_settings)):
    return {"status": "healthy", "version": "0.1.0", "env": settings.app_env}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
