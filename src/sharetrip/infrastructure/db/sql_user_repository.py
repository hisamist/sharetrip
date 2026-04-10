from sqlalchemy.orm import Session

from sharetrip.domain.entities.user import User
from sharetrip.domain.interfaces.user_repository import UserRepository
from sharetrip.infrastructure.db.models import UserORM


class SQLUserRepository(UserRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: int) -> User | None:
        row = self._session.get(UserORM, user_id)
        return self._to_domain(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        row = self._session.query(UserORM).filter(UserORM.email == email).first()
        return self._to_domain(row) if row else None

    def get_by_username(self, username: str) -> User | None:
        row = self._session.query(UserORM).filter(UserORM.username == username).first()
        return self._to_domain(row) if row else None

    def save(self, user: User) -> User:
        if user.id is None:
            row = UserORM(
                username=user.username,
                display_name=user.display_name,
                email=user.email,
                password_hash=user.password_hash,
                phone=user.phone,
            )
            self._session.add(row)
        else:
            row = self._session.get(UserORM, user.id)
            if row is None:
                raise ValueError(f"User {user.id} not found")
            row.username = user.username
            row.display_name = user.display_name
            row.email = user.email
            row.password_hash = user.password_hash
            row.phone = user.phone

        self._session.flush()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: UserORM) -> User:
        return User(
            id=row.id,
            username=row.username,
            display_name=row.display_name,
            email=row.email,
            password_hash=row.password_hash,
            phone=row.phone,
        )
