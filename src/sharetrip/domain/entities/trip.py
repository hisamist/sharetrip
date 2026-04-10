from enum import StrEnum

from pydantic import BaseModel, Field


class SettlementMethod(StrEnum):
    MINIMIZE_TRANSFERS = "minimize_transfers"
    DIRECT = "direct"


class RoundingStrategy(StrEnum):
    ROUND_HALF_UP = "round_half_up"
    FLOOR = "floor"
    CEIL = "ceil"


class Trip(BaseModel):
    name: str
    base_currency: str
    id: int | None = None
    settlement_method: SettlementMethod = SettlementMethod.MINIMIZE_TRANSFERS
    rounding_strategy: RoundingStrategy = RoundingStrategy.ROUND_HALF_UP
    budget_limit: float | None = Field(default=None, gt=0)
