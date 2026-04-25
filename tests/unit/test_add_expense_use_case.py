import pytest

from sharetrip.domain.entities.expense import Expense, ExpenseSplit, SplitType
from sharetrip.domain.entities.membership import Membership
from sharetrip.domain.entities.trip import Trip
from sharetrip.domain.interfaces.currency_port import CurrencyPort
from sharetrip.domain.interfaces.trip_repository import TripRepository
from sharetrip.domain.services.split_factory import SplitFactory
from sharetrip.use_cases.add_expense import AddExpenseInput, AddExpenseUseCase


# ─── Stubs ────────────────────────────────────────────────────────────────────


class StubCurrencyPort(CurrencyPort):
    def __init__(self, rate: float = 0.0061):
        self._rate = rate

    def get_rate(self, from_currency: str, to_currency: str) -> float:
        if from_currency == to_currency:
            return 1.0
        return self._rate


class StubTripRepository(TripRepository):
    def __init__(
        self, trip: Trip | None = None, members: list[Membership] | None = None
    ):
        self._trip = trip
        self._members = members or []
        self._expenses: list[Expense] = []
        self._splits: list[ExpenseSplit] = []
        self._next_expense_id = 1

    def get_trip(self, trip_id: int) -> Trip | None:
        return self._trip

    def list_trips(self) -> list[Trip]:
        return [self._trip] if self._trip else []

    def list_trips_for_user(self, user_id: int) -> list[Trip]:
        return [self._trip] if self._trip else []

    def save_trip(self, trip: Trip) -> Trip:
        self._trip = trip
        return trip

    def delete_trip(self, trip_id: int) -> None:
        self._trip = None

    def get_members(self, trip_id: int) -> list[Membership]:
        return self._members

    def add_member(self, membership: Membership) -> Membership:
        self._members.append(membership)
        return membership

    def remove_member(self, trip_id: int, user_id: int) -> None:
        self._members = [m for m in self._members if m.user_id != user_id]

    def get_expense(self, expense_id: int) -> Expense | None:
        return next((e for e in self._expenses if e.id == expense_id), None)

    def list_expenses(self, trip_id: int) -> list[Expense]:
        return [e for e in self._expenses if e.trip_id == trip_id]

    def save_expense(self, expense: Expense) -> Expense:
        saved = expense.model_copy(update={"id": self._next_expense_id})
        self._next_expense_id += 1
        self._expenses.append(saved)
        return saved

    def delete_expense(self, expense_id: int) -> None:
        self._expenses = [e for e in self._expenses if e.id != expense_id]

    def save_splits(self, splits: list[ExpenseSplit]) -> list[ExpenseSplit]:
        saved = [s.model_copy(update={"id": i + 1}) for i, s in enumerate(splits)]
        self._splits.extend(saved)
        return saved

    def get_splits(self, expense_id: int) -> list[ExpenseSplit]:
        return [s for s in self._splits if s.expense_id == expense_id]


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def trip() -> Trip:
    return Trip(id=1, name="Tokyo Trip", base_currency="EUR")


@pytest.fixture
def two_members() -> list[Membership]:
    return [Membership(trip_id=1, user_id=1), Membership(trip_id=1, user_id=2)]


@pytest.fixture
def use_case(trip, two_members) -> AddExpenseUseCase:
    return AddExpenseUseCase(
        trip_repository=StubTripRepository(trip=trip, members=two_members),
        currency_port=StubCurrencyPort(rate=0.0061),
        split_factory=SplitFactory(),
    )


def _input(**kwargs) -> AddExpenseInput:
    defaults = dict(
        trip_id=1,
        paid_by=1,
        title="Sushi",
        amount=5000.0,
        currency="JPY",
        split_type=SplitType.EQUAL,
    )
    return AddExpenseInput(**{**defaults, **kwargs})


# ─── Conversion devise ────────────────────────────────────────────────────────


class TestCurrencyConversion:
    def test_should_convert_amount_to_pivot_currency_when_currencies_differ(
        self, use_case
    ):
        output = use_case.execute(_input(amount=5000.0, currency="JPY"))
        assert output.expense.amount_pivot == pytest.approx(30.5)

    def test_should_store_exchange_rate_when_expense_created(self, use_case):
        output = use_case.execute(_input(amount=5000.0, currency="JPY"))
        assert output.expense.exchange_rate == pytest.approx(0.0061)

    def test_should_store_original_currency_when_expense_created(self, use_case):
        output = use_case.execute(_input(currency="JPY"))
        assert output.expense.original_currency == "JPY"

    def test_should_not_convert_when_currency_matches_trip_base(
        self, trip, two_members
    ):
        uc = AddExpenseUseCase(
            trip_repository=StubTripRepository(trip=trip, members=two_members),
            currency_port=StubCurrencyPort(),
            split_factory=SplitFactory(),
        )
        output = uc.execute(_input(amount=100.0, currency="EUR"))
        assert output.expense.amount_pivot == pytest.approx(100.0)


# ─── Persistance ──────────────────────────────────────────────────────────────


class TestPersistence:
    def test_should_assign_id_when_expense_saved(self, use_case):
        output = use_case.execute(_input())
        assert output.expense.id is not None

    def test_should_assign_ids_when_splits_saved(self, use_case):
        output = use_case.execute(_input())
        assert all(s.id is not None for s in output.splits)

    def test_should_create_one_split_per_member_when_equal_split(
        self, use_case, two_members
    ):
        output = use_case.execute(_input(split_type=SplitType.EQUAL))
        assert len(output.splits) == len(two_members)


# ─── Stratégies de split ──────────────────────────────────────────────────────


class TestSplitStrategies:
    def test_should_split_equally_when_split_type_is_equal(self, use_case):
        output = use_case.execute(_input(amount=5000.0, currency="JPY"))
        assert all(s.amount_owed == pytest.approx(15.25) for s in output.splits)

    def test_should_split_by_weight_when_split_type_is_percentage(self, trip):
        members = [
            Membership(trip_id=1, user_id=1, weight_percentage=60),
            Membership(trip_id=1, user_id=2, weight_percentage=40),
        ]
        uc = AddExpenseUseCase(
            trip_repository=StubTripRepository(trip=trip, members=members),
            currency_port=StubCurrencyPort(rate=1.0),
            split_factory=SplitFactory(),
        )
        output = uc.execute(
            _input(amount=100.0, currency="EUR", split_type=SplitType.PERCENTAGE)
        )
        amounts = {s.user_id: s.amount_owed for s in output.splits}
        assert amounts[1] == pytest.approx(60.0)
        assert amounts[2] == pytest.approx(40.0)

    def test_should_sum_splits_to_amount_pivot_when_expense_created(self, use_case):
        output = use_case.execute(_input(amount=5000.0, currency="JPY"))
        assert sum(s.amount_owed for s in output.splits) == pytest.approx(
            output.expense.amount_pivot
        )


# ─── Cas d'erreur ─────────────────────────────────────────────────────────────


class TestErrors:
    def test_should_raise_when_trip_not_found(self, two_members):
        uc = AddExpenseUseCase(
            trip_repository=StubTripRepository(trip=None, members=two_members),
            currency_port=StubCurrencyPort(),
            split_factory=SplitFactory(),
        )
        with pytest.raises(ValueError, match="not found"):
            uc.execute(_input())

    def test_should_raise_when_trip_has_no_members(self, trip):
        uc = AddExpenseUseCase(
            trip_repository=StubTripRepository(trip=trip, members=[]),
            currency_port=StubCurrencyPort(),
            split_factory=SplitFactory(),
        )
        with pytest.raises(ValueError, match="no members"):
            uc.execute(_input())
