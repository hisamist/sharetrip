from abc import ABC, abstractmethod

from sharetrip.domain.entities.expense import Expense, ExpenseSplit
from sharetrip.domain.entities.membership import Membership
from sharetrip.domain.entities.trip import Trip


class TripRepository(ABC):
    # ─── Trip ─────────────────────────────────────────────────────────────────

    @abstractmethod
    def get_trip(self, trip_id: int) -> Trip | None: ...

    @abstractmethod
    def list_trips(self) -> list[Trip]: ...

    @abstractmethod
    def save_trip(self, trip: Trip) -> Trip: ...

    @abstractmethod
    def delete_trip(self, trip_id: int) -> None: ...

    # ─── Members ──────────────────────────────────────────────────────────────

    @abstractmethod
    def get_members(self, trip_id: int) -> list[Membership]: ...

    @abstractmethod
    def add_member(self, membership: Membership) -> Membership: ...

    @abstractmethod
    def remove_member(self, trip_id: int, user_id: int) -> None: ...

    # ─── Expense ──────────────────────────────────────────────────────────────

    @abstractmethod
    def get_expense(self, expense_id: int) -> Expense | None: ...

    @abstractmethod
    def list_expenses(self, trip_id: int) -> list[Expense]: ...

    @abstractmethod
    def save_expense(self, expense: Expense) -> Expense: ...

    @abstractmethod
    def delete_expense(self, expense_id: int) -> None: ...

    # ─── Splits ───────────────────────────────────────────────────────────────

    @abstractmethod
    def save_splits(self, splits: list[ExpenseSplit]) -> list[ExpenseSplit]: ...

    @abstractmethod
    def get_splits(self, expense_id: int) -> list[ExpenseSplit]: ...
