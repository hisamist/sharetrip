from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from sharetrip.api.dependencies import get_current_user, get_db_session, get_jwt_service
from sharetrip.api.limiter import limiter
from sharetrip.api.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from sharetrip.domain.entities.user import User
from sharetrip.infrastructure.auth.jwt_service import JWTService
from sharetrip.infrastructure.auth.password_service import PasswordService
from sharetrip.infrastructure.db.sql_user_repository import SQLUserRepository
from sharetrip.use_cases.login_user import LoginInput, LoginUseCase
from sharetrip.use_cases.register_user import RegisterInput, RegisterUseCase

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
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


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
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


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        display_name=current_user.display_name,
        email=current_user.email,
    )
