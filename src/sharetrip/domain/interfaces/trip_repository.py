from abc import ABC, abstractmethod

from sharetrip.domain.entities.expense import Expense, ExpenseSplit
from sharetrip.domain.entities.membership import Membership
from sharetrip.domain.entities.trip import Trip


class TripRepository(ABC):
    @abstractmethod
    def get_trip(self, trip_id: int) -> Trip | None: ...

    @abstractmethod
    def save_trip(self, trip: Trip) -> Trip: ...

    @abstractmethod
    def get_members(self, trip_id: int) -> list[Membership]: ...

    @abstractmethod
    def get_expense(self, expense_id: int) -> Expense | None: ...

    @abstractmethod
    def save_expense(self, expense: Expense) -> Expense: ...

    @abstractmethod
    def save_splits(self, splits: list[ExpenseSplit]) -> list[ExpenseSplit]: ...
