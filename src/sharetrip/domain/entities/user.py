from pydantic import BaseModel, EmailStr


class User(BaseModel):
    username: str
    display_name: str
    email: EmailStr
    password_hash: str
    id: int | None = None
    phone: str | None = None
