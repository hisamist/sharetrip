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

    def list_trips_for_user(self, user_id: int) -> list[Trip]:
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
        result = ComputeSettlementsUseCase(repo).execute(ComputeSettlementsInput(trip_id=1))
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
        result = ComputeSettlementsUseCase(repo).execute(ComputeSettlementsInput(trip_id=1))

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
        result = ComputeSettlementsUseCase(repo).execute(ComputeSettlementsInput(trip_id=1))

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
        result = ComputeSettlementsUseCase(repo).execute(ComputeSettlementsInput(trip_id=1))

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
        result = ComputeSettlementsUseCase(repo).execute(ComputeSettlementsInput(trip_id=1))

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
        result = ComputeSettlementsUseCase(repo).execute(ComputeSettlementsInput(trip_id=1))

        total_transferred = sum(t.amount for t in result.transfers)
        assert abs(total_transferred - 200.0) < 0.01

    def test_should_return_no_transfers_when_single_member_paid_for_themselves(self):
        """Alice is alone in the trip and paid for herself only."""
        expense = _expense(expense_id=1, paid_by=1, amount=100.0)
        splits = {1: [_split(1, user_id=1, amount_owed=100.0)]}
        repo = StubTripRepository(trip=_trip(), expenses=[expense], splits=splits)
        result = ComputeSettlementsUseCase(repo).execute(ComputeSettlementsInput(trip_id=1))
        assert result.transfers == []

    def test_should_produce_three_transfers_for_four_person_trip_with_one_payer(self):
        """A pays 200 for all 4 (50 each) → 3 transfers: B, C, D → A."""
        expense = _expense(expense_id=1, paid_by=1, amount=200.0)
        splits = {
            1: [
                _split(1, user_id=1, amount_owed=50.0),
                _split(1, user_id=2, amount_owed=50.0),
                _split(1, user_id=3, amount_owed=50.0),
                _split(1, user_id=4, amount_owed=50.0),
            ]
        }
        repo = StubTripRepository(trip=_trip(), expenses=[expense], splits=splits)
        result = ComputeSettlementsUseCase(repo).execute(ComputeSettlementsInput(trip_id=1))

        assert len(result.transfers) == 3
        assert all(t.to_user_id == 1 for t in result.transfers)
        assert abs(sum(t.amount for t in result.transfers) - 150.0) < 0.01

    def test_should_not_create_cross_transfers_when_debts_are_independent(self):
        """
        A pays 100 for A+C only: A=+50, C=-50
        B pays 100 for B+D only: B=+50, D=-50
        Expected: C→A and D→B — no C→B or D→A.
        """
        e1 = _expense(expense_id=1, paid_by=1, amount=100.0)
        e2 = _expense(expense_id=2, paid_by=2, amount=100.0)
        splits = {
            1: [_split(1, user_id=1, amount_owed=50.0), _split(1, user_id=3, amount_owed=50.0)],
            2: [_split(2, user_id=2, amount_owed=50.0), _split(2, user_id=4, amount_owed=50.0)],
        }
        repo = StubTripRepository(trip=_trip(), expenses=[e1, e2], splits=splits)
        result = ComputeSettlementsUseCase(repo).execute(ComputeSettlementsInput(trip_id=1))

        assert len(result.transfers) == 2
        pairs = {(t.from_user_id, t.to_user_id) for t in result.transfers}
        assert (3, 1) in pairs  # C → A
        assert (4, 2) in pairs  # D → B

    def test_should_collapse_chain_debt_into_direct_transfer(self):
        """
        A pays 30 only for B (B owes A 30).
        B pays 30 only for C (C owes B 30).
        Net: A=+30, B=0, C=-30 → single transfer C→A 30, not C→B→A.
        """
        e1 = _expense(expense_id=1, paid_by=1, amount=30.0)
        e2 = _expense(expense_id=2, paid_by=2, amount=30.0)
        splits = {
            1: [_split(1, user_id=2, amount_owed=30.0)],  # B owes A
            2: [_split(2, user_id=3, amount_owed=30.0)],  # C owes B
        }
        repo = StubTripRepository(trip=_trip(), expenses=[e1, e2], splits=splits)
        result = ComputeSettlementsUseCase(repo).execute(ComputeSettlementsInput(trip_id=1))

        assert len(result.transfers) == 1
        t = result.transfers[0]
        assert t.from_user_id == 3
        assert t.to_user_id == 1
        assert abs(t.amount - 30.0) < 0.01

    def test_should_return_no_transfers_when_all_paid_symmetrically(self):
        """Each person pays for everyone equally → all balances = 0."""
        expenses = [_expense(expense_id=i, paid_by=i, amount=30.0) for i in range(1, 4)]
        splits = {
            i: [_split(i, user_id=u, amount_owed=10.0) for u in range(1, 4)]
            for i in range(1, 4)
        }
        repo = StubTripRepository(trip=_trip(), expenses=expenses, splits=splits)
        result = ComputeSettlementsUseCase(repo).execute(ComputeSettlementsInput(trip_id=1))
        assert result.transfers == []

    def test_should_conserve_total_money_in_all_transfers(self):
        """sum(transfers) must equal the net debt of all debtors."""
        expense = _expense(expense_id=1, paid_by=1, amount=300.0)
        splits = {
            1: [
                _split(1, user_id=1, amount_owed=75.0),
                _split(1, user_id=2, amount_owed=75.0),
                _split(1, user_id=3, amount_owed=75.0),
                _split(1, user_id=4, amount_owed=75.0),
            ]
        }
        repo = StubTripRepository(trip=_trip(), expenses=[expense], splits=splits)
        result = ComputeSettlementsUseCase(repo).execute(ComputeSettlementsInput(trip_id=1))

        # A paid 300, owes 75 herself → is owed 225 by B, C, D
        assert abs(sum(t.amount for t in result.transfers) - 225.0) < 0.01
