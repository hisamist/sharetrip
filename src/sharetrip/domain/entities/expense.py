from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class SplitType(StrEnum):
    EQUAL = "equal"
    PERCENTAGE = "percentage"
    HYBRID = "hybrid"


class ExpenseSplit(BaseModel):
    expense_id: int | None
    user_id: int
    share_ratio: float = Field(gt=0)
    id: int | None = None
    amount_owed: float = 0.0


class Expense(BaseModel):
    trip_id: int
    paid_by: int
    title: str
    amount_pivot: float = Field(gt=0)
    split_type: SplitType
    id: int | None = None
    category: str | None = None
    original_currency: str | None = None
    exchange_rate: float = Field(default=1.0, gt=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    splits: list[ExpenseSplit] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_splits_not_empty_for_hybrid(self) -> "Expense":
        if self.split_type == SplitType.HYBRID and not self.splits:
            raise ValueError("Hybrid split requires at least one ExpenseSplit")
        return self
