import pytest

from sharetrip.domain.entities.user import User
from sharetrip.domain.interfaces.user_repository import UserRepository
from sharetrip.infrastructure.auth.jwt_service import JWTService
from sharetrip.infrastructure.auth.password_service import PasswordService
from sharetrip.use_cases.login_user import LoginInput, LoginUseCase
from sharetrip.use_cases.register_user import RegisterInput, RegisterUseCase


# ─── Stubs ────────────────────────────────────────────────────────────────────


class StubUserRepository(UserRepository):
    def __init__(self, users: list[User] | None = None) -> None:
        self._users: list[User] = users or []
        self._next_id = len(self._users) + 1

    def get_by_id(self, user_id: int) -> User | None:
        return next((u for u in self._users if u.id == user_id), None)

    def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._users if u.email == email), None)

    def get_by_username(self, username: str) -> User | None:
        return next((u for u in self._users if u.username == username), None)

    def save(self, user: User) -> User:
        saved = user.model_copy(update={"id": self._next_id})
        self._users.append(saved)
        self._next_id += 1
        return saved


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def password_service() -> PasswordService:
    return PasswordService()


@pytest.fixture()
def jwt_service() -> JWTService:
    return JWTService(secret_key="test-secret")


@pytest.fixture()
def empty_repo() -> StubUserRepository:
    return StubUserRepository()


@pytest.fixture()
def existing_user(password_service: PasswordService) -> User:
    return User(
        id=1,
        username="alice",
        display_name="Alice",
        email="alice@example.com",
        password_hash=password_service.hash("correct-password"),
    )


@pytest.fixture()
def repo_with_user(existing_user: User) -> StubUserRepository:
    return StubUserRepository(users=[existing_user])


# ─── RegisterUseCase ──────────────────────────────────────────────────────────


class TestRegisterUseCase:
    def test_should_return_saved_user_when_registration_is_valid(
        self, empty_repo: StubUserRepository, password_service: PasswordService
    ):
        use_case = RegisterUseCase(
            user_repository=empty_repo, password_service=password_service
        )
        result = use_case.execute(
            RegisterInput(
                username="bob",
                display_name="Bob",
                email="bob@example.com",
                password="s3cr3t",
            )
        )

        assert result.id is not None
        assert result.username == "bob"
        assert result.display_name == "Bob"
        assert result.email == "bob@example.com"

    def test_should_hash_password_when_user_is_registered(
        self, empty_repo: StubUserRepository, password_service: PasswordService
    ):
        use_case = RegisterUseCase(
            user_repository=empty_repo, password_service=password_service
        )
        result = use_case.execute(
            RegisterInput(
                username="bob",
                display_name="Bob",
                email="bob@example.com",
                password="plaintext",
            )
        )

        assert result.password_hash != "plaintext"
        assert password_service.verify("plaintext", result.password_hash)

    def test_should_persist_optional_phone_when_provided(
        self, empty_repo: StubUserRepository, password_service: PasswordService
    ):
        use_case = RegisterUseCase(
            user_repository=empty_repo, password_service=password_service
        )
        result = use_case.execute(
            RegisterInput(
                username="bob",
                display_name="Bob",
                email="bob@example.com",
                password="s3cr3t",
                phone="+33612345678",
            )
        )

        assert result.phone == "+33612345678"

    def test_should_raise_when_email_already_registered(
        self, repo_with_user: StubUserRepository, password_service: PasswordService
    ):
        use_case = RegisterUseCase(
            user_repository=repo_with_user, password_service=password_service
        )
        with pytest.raises(ValueError, match="already registered"):
            use_case.execute(
                RegisterInput(
                    username="other",
                    display_name="Other",
                    email="alice@example.com",
                    password="s3cr3t",
                )
            )

    def test_should_raise_when_username_already_taken(
        self, repo_with_user: StubUserRepository, password_service: PasswordService
    ):
        use_case = RegisterUseCase(
            user_repository=repo_with_user, password_service=password_service
        )
        with pytest.raises(ValueError, match="already taken"):
            use_case.execute(
                RegisterInput(
                    username="alice",
                    display_name="Other Alice",
                    email="other@example.com",
                    password="s3cr3t",
                )
            )

    def test_should_store_user_in_repository_when_registration_succeeds(
        self, empty_repo: StubUserRepository, password_service: PasswordService
    ):
        use_case = RegisterUseCase(
            user_repository=empty_repo, password_service=password_service
        )
        use_case.execute(
            RegisterInput(
                username="carol",
                display_name="Carol",
                email="carol@example.com",
                password="s3cr3t",
            )
        )

        assert empty_repo.get_by_email("carol@example.com") is not None


# ─── LoginUseCase ─────────────────────────────────────────────────────────────


class TestLoginUseCase:
    def test_should_return_access_token_when_credentials_are_valid(
        self,
        repo_with_user: StubUserRepository,
        password_service: PasswordService,
        jwt_service: JWTService,
    ):
        use_case = LoginUseCase(
            user_repository=repo_with_user,
            password_service=password_service,
            jwt_service=jwt_service,
        )
        result = use_case.execute(
            LoginInput(email="alice@example.com", password="correct-password")
        )

        assert result.access_token
        assert result.token_type == "bearer"

    def test_should_encode_user_id_in_token_when_login_succeeds(
        self,
        repo_with_user: StubUserRepository,
        password_service: PasswordService,
        jwt_service: JWTService,
    ):
        use_case = LoginUseCase(
            user_repository=repo_with_user,
            password_service=password_service,
            jwt_service=jwt_service,
        )
        result = use_case.execute(
            LoginInput(email="alice@example.com", password="correct-password")
        )

        payload = jwt_service.decode_token(result.access_token)
        assert payload["sub"] == "1"
        assert payload["email"] == "alice@example.com"

    def test_should_raise_when_email_does_not_exist(
        self,
        empty_repo: StubUserRepository,
        password_service: PasswordService,
        jwt_service: JWTService,
    ):
        use_case = LoginUseCase(
            user_repository=empty_repo,
            password_service=password_service,
            jwt_service=jwt_service,
        )
        with pytest.raises(ValueError, match="Invalid email or password"):
            use_case.execute(LoginInput(email="nobody@example.com", password="any"))

    def test_should_raise_when_password_is_wrong(
        self,
        repo_with_user: StubUserRepository,
        password_service: PasswordService,
        jwt_service: JWTService,
    ):
        use_case = LoginUseCase(
            user_repository=repo_with_user,
            password_service=password_service,
            jwt_service=jwt_service,
        )
        with pytest.raises(ValueError, match="Invalid email or password"):
            use_case.execute(
                LoginInput(email="alice@example.com", password="wrong-password")
            )

    def test_should_not_distinguish_between_wrong_email_and_wrong_password(
        self,
        repo_with_user: StubUserRepository,
        password_service: PasswordService,
        jwt_service: JWTService,
    ):
        """Both failures must return the same error message to prevent user enumeration."""
        use_case = LoginUseCase(
            user_repository=repo_with_user,
            password_service=password_service,
            jwt_service=jwt_service,
        )
        with pytest.raises(
            ValueError, match="Invalid email or password"
        ) as exc_wrong_email:
            use_case.execute(LoginInput(email="nobody@example.com", password="any"))
        with pytest.raises(
            ValueError, match="Invalid email or password"
        ) as exc_wrong_pass:
            use_case.execute(LoginInput(email="alice@example.com", password="wrong"))

        assert str(exc_wrong_email.value) == str(exc_wrong_pass.value)
