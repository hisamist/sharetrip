from abc import ABC, abstractmethod

from sharetrip.domain.entities.expense import Expense
from sharetrip.domain.entities.trip import Trip


class ExpenseObserver(ABC):
    @abstractmethod
    def on_expense_created(self, expense: Expense, trip: Trip) -> None:
        """Called after an expense is persisted and splits are computed."""
