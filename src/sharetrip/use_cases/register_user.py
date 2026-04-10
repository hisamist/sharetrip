from dataclasses import dataclass

from sharetrip.domain.entities.user import User
from sharetrip.domain.interfaces.user_repository import UserRepository
from sharetrip.infrastructure.auth.password_service import PasswordService


@dataclass
class RegisterInput:
    username: str
    display_name: str
    email: str
    password: str
    phone: str | None = None


class RegisterUseCase:
    def __init__(
        self, user_repository: UserRepository, password_service: PasswordService
    ) -> None:
        self._repo = user_repository
        self._passwords = password_service

    def execute(self, input: RegisterInput) -> User:
        if self._repo.get_by_email(input.email) is not None:
            raise ValueError(f"Email {input.email} already registered")

        if self._repo.get_by_username(input.username) is not None:
            raise ValueError(f"Username {input.username} already taken")

        user = User(
            username=input.username,
            display_name=input.display_name,
            email=input.email,
            password_hash=self._passwords.hash(input.password),
            phone=input.phone,
        )
        return self._repo.save(user)
