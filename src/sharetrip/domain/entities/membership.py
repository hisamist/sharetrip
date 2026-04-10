from enum import StrEnum

from pydantic import BaseModel, Field


class MemberRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class Membership(BaseModel):
    trip_id: int
    user_id: int
    role: MemberRole = MemberRole.MEMBER
    weight_percentage: float = Field(default=1.0, gt=0, le=100)
