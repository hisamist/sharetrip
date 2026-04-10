from pydantic import BaseModel

from sharetrip.domain.entities.expense import SplitType


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


class TransferResponse(BaseModel):
    from_user_id: int
    to_user_id: int
    amount: float
