from datetime import UTC, datetime, timedelta

import jwt

_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24h


class JWTService:
    def __init__(self, secret_key: str) -> None:
        self._secret = secret_key

    def create_access_token(self, user_id: int, email: str) -> str:
        payload = {
            "sub": str(user_id),
            "email": email,
            "exp": datetime.now(UTC) + timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES),
        }
        return jwt.encode(payload, self._secret, algorithm=_ALGORITHM)

    def decode_token(self, token: str) -> dict:
        """Retourne le payload décodé ou lève jwt.InvalidTokenError."""
        return jwt.decode(token, self._secret, algorithms=[_ALGORITHM])
