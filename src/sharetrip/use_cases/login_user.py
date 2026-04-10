from dataclasses import dataclass

from sharetrip.domain.interfaces.user_repository import UserRepository
from sharetrip.infrastructure.auth.jwt_service import JWTService
from sharetrip.infrastructure.auth.password_service import PasswordService


@dataclass
class LoginInput:
    email: str
    password: str


@dataclass
class LoginOutput:
    access_token: str
    token_type: str = "bearer"


class LoginUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        password_service: PasswordService,
        jwt_service: JWTService,
    ) -> None:
        self._repo = user_repository
        self._passwords = password_service
        self._jwt = jwt_service

    def execute(self, input: LoginInput) -> LoginOutput:
        user = self._repo.get_by_email(input.email)
        if user is None or not self._passwords.verify(
            input.password, user.password_hash
        ):
            raise ValueError("Invalid email or password")

        token = self._jwt.create_access_token(user_id=user.id, email=user.email)
        return LoginOutput(access_token=token)
