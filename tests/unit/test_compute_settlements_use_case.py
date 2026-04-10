import pytest

from sharetrip.domain.entities.expense import Expense, ExpenseSplit, SplitType
from sharetrip.domain.entities.membership import Membership
from sharetrip.domain.entities.trip import Trip
from sharetrip.domain.interfaces.trip_repository import TripRepository
from sharetrip.use_cases.compute_settlements import (
    ComputeSettlementsInput,
    ComputeSettlementsUseCase,
)


# ─── Stub ─────────────────────────────────────────────────────────────────────


class StubTripRepository(TripRepository):
    def __init__(
        self,
        trip: Trip | None,
        expenses: list[Expense],
        splits: dict[int, list[ExpenseSplit]],
    ):
        self._trip = trip
        self._expenses = expenses
        self._splits = splits

    def get_trip(self, trip_id: int) -> Trip | None:
        return self._trip

    def list_trips(self) -> list[Trip]:
        return [self._trip] if self._trip else []

    def save_trip(self, trip: Trip) -> Trip:
        return trip

    def delete_trip(self, trip_id: int) -> None:
        pass

    def get_members(self, trip_id: int) -> list[Membership]:
        return []

    def add_member(self, membership: Membership) -> Membership:
        return membership

    def remove_member(self, trip_id: int, user_id: int) -> None:
        pass

    def get_expense(self, expense_id: int) -> Expense | None:
        return next((e for e in self._expenses if e.id == expense_id), None)

    def list_expenses(self, trip_id: int) -> list[Expense]:
        return self._expenses

    def save_expense(self, expense: Expense) -> Expense:
        return expense

    def delete_expense(self, expense_id: int) -> None:
        pass

    def save_splits(self, splits: list[ExpenseSplit]) -> list[ExpenseSplit]:
        return splits

    def get_splits(self, expense_id: int) -> list[ExpenseSplit]:
        return self._splits.get(expense_id, [])


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _trip() -> Trip:
    return Trip(id=1, name="Test", base_currency="EUR")


def _expense(expense_id: int, paid_by: int, amount: float) -> Expense:
    return Expense(
        id=expense_id,
        trip_id=1,
        paid_by=paid_by,
        title="Expense",
        amount_pivot=amount,
        split_type=SplitType.EQUAL,
    )


def _split(expense_id: int, user_id: int, amount_owed: float) -> ExpenseSplit:
    return ExpenseSplit(
        id=None,
        expense_id=expense_id,
        user_id=user_id,
        share_ratio=1.0,
        amount_owed=amount_owed,
    )


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestComputeSettlementsUseCase:
    def test_should_return_no_transfers_when_trip_has_no_expenses(self):
        repo = StubTripRepository(trip=_trip(), expenses=[], splits={})
        result = ComputeSettlementsUseCase(repo).execute(
            ComputeSettlementsInput(trip_id=1)
        )
        assert result.transfers == []

    def test_should_raise_when_trip_does_not_exist(self):
        repo = StubTripRepository(trip=None, expenses=[], splits={})
        with pytest.raises(ValueError, match="not found"):
            ComputeSettlementsUseCase(repo).execute(ComputeSettlementsInput(trip_id=99))

    def test_should_return_one_transfer_when_one_user_paid_for_two(self):
        """Alice (1) paid 100, split equally → Bob (2) owes Alice 50."""
        expense = _expense(expense_id=1, paid_by=1, amount=100.0)
        splits = {
            1: [
                _split(1, user_id=1, amount_owed=50.0),
                _split(1, user_id=2, amount_owed=50.0),
            ]
        }
        repo = StubTripRepository(trip=_trip(), expenses=[expense], splits=splits)
        result = ComputeSettlementsUseCase(repo).execute(
            ComputeSettlementsInput(trip_id=1)
        )

        assert len(result.transfers) == 1
        t = result.transfers[0]
        assert t.from_user_id == 2
        assert t.to_user_id == 1
        assert abs(t.amount - 50.0) < 0.01

    def test_should_return_no_transfers_when_balances_are_even(self):
        """Alice paid 60, Bob paid 60, each split equally → zero balance."""
        e1 = _expense(expense_id=1, paid_by=1, amount=60.0)
        e2 = _expense(expense_id=2, paid_by=2, amount=60.0)
        splits = {
            1: [_split(1, 1, 30.0), _split(1, 2, 30.0)],
            2: [_split(2, 1, 30.0), _split(2, 2, 30.0)],
        }
        repo = StubTripRepository(trip=_trip(), expenses=[e1, e2], splits=splits)
        result = ComputeSettlementsUseCase(repo).execute(
            ComputeSettlementsInput(trip_id=1)
        )

        assert result.transfers == []

    def test_should_minimize_transfers_for_three_users(self):
        """
        Alice (1) paid 90 split equally 3 ways (30 each).
        Net: Alice +60, Bob -30, Carol -30.
        Expected: Bob→Alice 30, Carol→Alice 30 (2 transfers).
        """
        expense = _expense(expense_id=1, paid_by=1, amount=90.0)
        splits = {
            1: [
                _split(1, user_id=1, amount_owed=30.0),
                _split(1, user_id=2, amount_owed=30.0),
                _split(1, user_id=3, amount_owed=30.0),
            ]
        }
        repo = StubTripRepository(trip=_trip(), expenses=[expense], splits=splits)
        result = ComputeSettlementsUseCase(repo).execute(
            ComputeSettlementsInput(trip_id=1)
        )

        assert len(result.transfers) == 2
        assert all(t.to_user_id == 1 for t in result.transfers)
        assert abs(sum(t.amount for t in result.transfers) - 60.0) < 0.01

    def test_should_produce_single_transfer_when_cross_debts_cancel_partially(self):
        """
        Alice (1) paid 120 split 50/50 with Bob (2).
        Bob (2) paid 40 split 50/50 with Alice (1).
        Net: Alice +60-20=+40, Bob -60+20=-40.
        Expected: one transfer Bob→Alice 40.
        """
        e1 = _expense(expense_id=1, paid_by=1, amount=120.0)
        e2 = _expense(expense_id=2, paid_by=2, amount=40.0)
        splits = {
            1: [_split(1, 1, 60.0), _split(1, 2, 60.0)],
            2: [_split(2, 1, 20.0), _split(2, 2, 20.0)],
        }
        repo = StubTripRepository(trip=_trip(), expenses=[e1, e2], splits=splits)
        result = ComputeSettlementsUseCase(repo).execute(
            ComputeSettlementsInput(trip_id=1)
        )

        assert len(result.transfers) == 1
        t = result.transfers[0]
        assert t.from_user_id == 2
        assert t.to_user_id == 1
        assert abs(t.amount - 40.0) < 0.01

    def test_should_return_correct_total_amount_across_all_transfers(self):
        """Sum of all transfer amounts equals sum of what debtors owe."""
        expense = _expense(expense_id=1, paid_by=1, amount=300.0)
        splits = {
            1: [
                _split(1, user_id=1, amount_owed=100.0),
                _split(1, user_id=2, amount_owed=100.0),
                _split(1, user_id=3, amount_owed=100.0),
            ]
        }
        repo = StubTripRepository(trip=_trip(), expenses=[expense], splits=splits)
        result = ComputeSettlementsUseCase(repo).execute(
            ComputeSettlementsInput(trip_id=1)
        )

        total_transferred = sum(t.amount for t in result.transfers)
        assert abs(total_transferred - 200.0) < 0.01
