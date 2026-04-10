import logging

import pytest

from sharetrip.domain.entities.expense import Expense, ExpenseSplit, SplitType
from sharetrip.domain.entities.membership import Membership
from sharetrip.domain.entities.trip import Trip
from sharetrip.domain.interfaces.currency_port import CurrencyPort
from sharetrip.domain.interfaces.expense_observer import ExpenseObserver
from sharetrip.domain.interfaces.trip_repository import TripRepository
from sharetrip.domain.services.split_factory import SplitFactory
from sharetrip.infrastructure.notifications.log_observer import LogNotificationObserver
from sharetrip.use_cases.add_expense import AddExpenseInput, AddExpenseUseCase


# ─── Stubs ────────────────────────────────────────────────────────────────────


class SpyObserver(ExpenseObserver):
    """Captures calls to verify Observer contract."""

    def __init__(self):
        self.calls: list[tuple[Expense, Trip]] = []

    def on_expense_created(self, expense: Expense, trip: Trip) -> None:
        self.calls.append((expense, trip))


class StubCurrencyPort(CurrencyPort):
    def get_rate(self, from_currency: str, to_currency: str) -> float:
        return 1.0


class StubTripRepository(TripRepository):
    def __init__(self, trip: Trip, members: list[Membership]):
        self._trip = trip
        self._members = members
        self._expenses: list[Expense] = []
        self._splits: list[ExpenseSplit] = []
        self._next_id = 1

    def get_trip(self, trip_id: int) -> Trip | None:
        return self._trip

    def list_trips(self) -> list[Trip]:
        return [self._trip]

    def save_trip(self, trip: Trip) -> Trip:
        return trip

    def delete_trip(self, trip_id: int) -> None:
        pass

    def get_members(self, trip_id: int) -> list[Membership]:
        return self._members

    def add_member(self, membership: Membership) -> Membership:
        return membership

    def remove_member(self, trip_id: int, user_id: int) -> None:
        pass

    def get_expense(self, expense_id: int) -> Expense | None:
        return next((e for e in self._expenses if e.id == expense_id), None)

    def list_expenses(self, trip_id: int) -> list[Expense]:
        return self._expenses

    def save_expense(self, expense: Expense) -> Expense:
        saved = expense.model_copy(update={"id": self._next_id})
        self._expenses.append(saved)
        self._next_id += 1
        return saved

    def delete_expense(self, expense_id: int) -> None:
        pass

    def save_splits(self, splits: list[ExpenseSplit]) -> list[ExpenseSplit]:
        self._splits.extend(splits)
        return splits

    def get_splits(self, expense_id: int) -> list[ExpenseSplit]:
        return [s for s in self._splits if s.expense_id == expense_id]


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def trip():
    return Trip(id=1, name="Tokyo", base_currency="EUR")


@pytest.fixture()
def trip_with_budget():
    return Trip(id=1, name="Tokyo", base_currency="EUR", budget_limit=100.0)


@pytest.fixture()
def members():
    return [
        Membership(trip_id=1, user_id=1),
        Membership(trip_id=1, user_id=2),
    ]


@pytest.fixture()
def expense_input():
    return AddExpenseInput(
        trip_id=1,
        paid_by=1,
        title="Sushi",
        amount=60.0,
        currency="EUR",
        split_type=SplitType.EQUAL,
    )


# ─── Observer contract ────────────────────────────────────────────────────────


class TestExpenseObserverContract:
    def test_should_call_observer_once_when_expense_is_created(
        self, trip, members, expense_input
    ):
        spy = SpyObserver()
        repo = StubTripRepository(trip=trip, members=members)
        use_case = AddExpenseUseCase(
            trip_repository=repo,
            currency_port=StubCurrencyPort(),
            split_factory=SplitFactory(),
            observers=[spy],
        )
        use_case.execute(expense_input)

        assert len(spy.calls) == 1

    def test_should_pass_saved_expense_to_observer(self, trip, members, expense_input):
        spy = SpyObserver()
        repo = StubTripRepository(trip=trip, members=members)
        use_case = AddExpenseUseCase(
            trip_repository=repo,
            currency_port=StubCurrencyPort(),
            split_factory=SplitFactory(),
            observers=[spy],
        )
        use_case.execute(expense_input)

        observed_expense, _ = spy.calls[0]
        assert observed_expense.id is not None
        assert observed_expense.title == "Sushi"
        assert observed_expense.amount_pivot == 60.0

    def test_should_pass_trip_to_observer(self, trip, members, expense_input):
        spy = SpyObserver()
        repo = StubTripRepository(trip=trip, members=members)
        use_case = AddExpenseUseCase(
            trip_repository=repo,
            currency_port=StubCurrencyPort(),
            split_factory=SplitFactory(),
            observers=[spy],
        )
        use_case.execute(expense_input)

        _, observed_trip = spy.calls[0]
        assert observed_trip.id == trip.id
        assert observed_trip.name == trip.name

    def test_should_call_all_observers_when_multiple_registered(
        self, trip, members, expense_input
    ):
        spy1, spy2 = SpyObserver(), SpyObserver()
        repo = StubTripRepository(trip=trip, members=members)
        use_case = AddExpenseUseCase(
            trip_repository=repo,
            currency_port=StubCurrencyPort(),
            split_factory=SplitFactory(),
            observers=[spy1, spy2],
        )
        use_case.execute(expense_input)

        assert len(spy1.calls) == 1
        assert len(spy2.calls) == 1

    def test_should_not_call_observer_when_none_registered(
        self, trip, members, expense_input
    ):
        spy = SpyObserver()
        repo = StubTripRepository(trip=trip, members=members)
        use_case = AddExpenseUseCase(
            trip_repository=repo,
            currency_port=StubCurrencyPort(),
            split_factory=SplitFactory(),
            observers=[],
        )
        use_case.execute(expense_input)

        assert spy.calls == []


# ─── LogNotificationObserver ──────────────────────────────────────────────────


class TestLogNotificationObserver:
    def _expense(self, amount: float = 50.0) -> Expense:
        return Expense(
            id=1,
            trip_id=1,
            paid_by=1,
            title="Test",
            amount_pivot=amount,
            split_type=SplitType.EQUAL,
        )

    def test_should_log_info_when_no_budget_limit(self, trip, caplog):
        observer = LogNotificationObserver()
        with caplog.at_level(logging.INFO):
            observer.on_expense_created(self._expense(), trip)

        assert any("Expense added" in r.message for r in caplog.records)

    def test_should_log_info_when_under_budget(self, trip_with_budget, caplog):
        observer = LogNotificationObserver()
        with caplog.at_level(logging.INFO):
            observer.on_expense_created(self._expense(amount=40.0), trip_with_budget)

        assert any("remaining" in r.message for r in caplog.records)
        assert not any(r.levelno == logging.WARNING for r in caplog.records)

    def test_should_log_warning_when_budget_exceeded(self, trip_with_budget, caplog):
        observer = LogNotificationObserver()
        with caplog.at_level(logging.WARNING):
            observer.on_expense_created(self._expense(amount=150.0), trip_with_budget)

        assert any(r.levelno == logging.WARNING for r in caplog.records)
        assert any("exceeded" in r.message for r in caplog.records)
