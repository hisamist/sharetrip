import pytest

from sharetrip.domain.entities.expense import Expense, ExpenseSplit, SplitType
from sharetrip.domain.entities.membership import Membership
from sharetrip.domain.entities.trip import Trip
from sharetrip.domain.interfaces.trip_repository import TripRepository
from sharetrip.infrastructure.cache.cached_trip_repository import (
    CachedTripRepository,
    _expense_key,
    _members_key,
    _trip_key,
)


# ─── Stubs ────────────────────────────────────────────────────────────────────


class FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    def get(self, key: str) -> bytes | None:
        value = self._store.get(key)
        return value.encode() if value is not None else None

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    def delete(self, *keys: str) -> None:
        for key in keys:
            self._store.pop(key, None)

    def has(self, key: str) -> bool:
        return key in self._store


class FakeTripRepository(TripRepository):
    def __init__(
        self, trip: Trip | None = None, members: list[Membership] | None = None
    ):
        self._trip = trip
        self._members = members or []
        self._expenses: list[Expense] = []
        self._splits: list[ExpenseSplit] = []
        self.call_counts: dict[str, int] = {}

    def _count(self, method: str) -> None:
        self.call_counts[method] = self.call_counts.get(method, 0) + 1

    def get_trip(self, trip_id: int) -> Trip | None:
        self._count("get_trip")
        return self._trip

    def list_trips(self) -> list[Trip]:
        self._count("list_trips")
        return [self._trip] if self._trip else []

    def save_trip(self, trip: Trip) -> Trip:
        self._count("save_trip")
        self._trip = trip
        return trip

    def delete_trip(self, trip_id: int) -> None:
        self._count("delete_trip")
        self._trip = None

    def get_members(self, trip_id: int) -> list[Membership]:
        self._count("get_members")
        return self._members

    def add_member(self, membership: Membership) -> Membership:
        self._count("add_member")
        self._members.append(membership)
        return membership

    def remove_member(self, trip_id: int, user_id: int) -> None:
        self._count("remove_member")
        self._members = [m for m in self._members if m.user_id != user_id]

    def get_expense(self, expense_id: int) -> Expense | None:
        self._count("get_expense")
        return next((e for e in self._expenses if e.id == expense_id), None)

    def list_expenses(self, trip_id: int) -> list[Expense]:
        self._count("list_expenses")
        return self._expenses

    def save_expense(self, expense: Expense) -> Expense:
        self._count("save_expense")
        if expense.id is not None:
            self._expenses = [e for e in self._expenses if e.id != expense.id]
            self._expenses.append(expense)
            return expense
        saved = expense.model_copy(update={"id": len(self._expenses) + 1})
        self._expenses.append(saved)
        return saved

    def delete_expense(self, expense_id: int) -> None:
        self._count("delete_expense")
        self._expenses = [e for e in self._expenses if e.id != expense_id]

    def save_splits(self, splits: list[ExpenseSplit]) -> list[ExpenseSplit]:
        self._count("save_splits")
        return splits

    def get_splits(self, expense_id: int) -> list[ExpenseSplit]:
        self._count("get_splits")
        return self._splits


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def trip() -> Trip:
    return Trip(id=1, name="Tokyo", base_currency="EUR")


@pytest.fixture
def members() -> list[Membership]:
    return [Membership(trip_id=1, user_id=1), Membership(trip_id=1, user_id=2)]


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def inner(trip, members) -> FakeTripRepository:
    return FakeTripRepository(trip=trip, members=members)


@pytest.fixture
def repo(inner, fake_redis) -> CachedTripRepository:
    return CachedTripRepository(inner=inner, redis=fake_redis)


# ─── get_trip ─────────────────────────────────────────────────────────────────


class TestGetTrip:
    def test_should_call_inner_when_trip_not_in_cache(self, repo, inner):
        repo.get_trip(1)
        assert inner.call_counts.get("get_trip") == 1

    def test_should_store_trip_in_redis_when_cache_miss(self, repo, fake_redis):
        repo.get_trip(1)
        assert fake_redis.has(_trip_key(1))

    def test_should_not_call_inner_when_trip_in_cache(self, repo, inner):
        repo.get_trip(1)  # miss
        repo.get_trip(1)  # hit
        assert inner.call_counts.get("get_trip") == 1

    def test_should_return_correct_trip_when_cache_hit(self, repo, trip):
        repo.get_trip(1)
        result = repo.get_trip(1)
        assert result.name == trip.name
        assert result.base_currency == trip.base_currency

    def test_should_return_none_when_trip_does_not_exist(self, fake_redis):
        repo = CachedTripRepository(
            inner=FakeTripRepository(trip=None), redis=fake_redis
        )
        assert repo.get_trip(99) is None

    def test_should_not_store_in_redis_when_trip_not_found(self, fake_redis):
        repo = CachedTripRepository(
            inner=FakeTripRepository(trip=None), redis=fake_redis
        )
        repo.get_trip(99)
        assert not fake_redis.has(_trip_key(99))


# ─── save_trip / delete_trip ──────────────────────────────────────────────────


class TestTripInvalidation:
    def test_should_invalidate_cache_when_trip_saved(self, repo, fake_redis):
        repo.get_trip(1)
        assert fake_redis.has(_trip_key(1))
        repo.save_trip(Trip(id=1, name="Updated", base_currency="USD"))
        assert not fake_redis.has(_trip_key(1))

    def test_should_invalidate_trip_and_members_cache_when_trip_deleted(
        self, repo, fake_redis
    ):
        repo.get_trip(1)
        repo.get_members(1)
        repo.delete_trip(1)
        assert not fake_redis.has(_trip_key(1))
        assert not fake_redis.has(_members_key(1))


# ─── get_members ──────────────────────────────────────────────────────────────


class TestGetMembers:
    def test_should_call_inner_when_members_not_in_cache(self, repo, inner):
        repo.get_members(1)
        assert inner.call_counts.get("get_members") == 1

    def test_should_not_call_inner_when_members_in_cache(self, repo, inner):
        repo.get_members(1)  # miss
        repo.get_members(1)  # hit
        assert inner.call_counts.get("get_members") == 1

    def test_should_return_correct_members_when_cache_hit(self, repo, members):
        repo.get_members(1)
        result = repo.get_members(1)
        assert {m.user_id for m in result} == {m.user_id for m in members}

    def test_should_invalidate_members_cache_when_member_added(self, repo, fake_redis):
        repo.get_members(1)
        repo.add_member(Membership(trip_id=1, user_id=99))
        assert not fake_redis.has(_members_key(1))

    def test_should_invalidate_members_cache_when_member_removed(
        self, repo, fake_redis
    ):
        repo.get_members(1)
        repo.remove_member(1, user_id=1)
        assert not fake_redis.has(_members_key(1))


# ─── get_expense ──────────────────────────────────────────────────────────────


class TestGetExpense:
    @pytest.fixture
    def saved_expense(self, inner) -> Expense:
        expense = Expense(
            id=1,
            trip_id=1,
            paid_by=1,
            title="Sushi",
            amount_pivot=30.5,
            split_type=SplitType.EQUAL,
        )
        inner._expenses.append(expense)
        return expense

    def test_should_call_inner_when_expense_not_in_cache(
        self, repo, inner, saved_expense
    ):
        repo.get_expense(1)
        assert inner.call_counts.get("get_expense") == 1

    def test_should_not_call_inner_when_expense_in_cache(
        self, repo, inner, saved_expense
    ):
        repo.get_expense(1)  # miss
        repo.get_expense(1)  # hit
        assert inner.call_counts.get("get_expense") == 1

    def test_should_invalidate_cache_when_expense_saved(
        self, repo, fake_redis, saved_expense
    ):
        repo.get_expense(1)
        repo.save_expense(saved_expense.model_copy(update={"title": "Updated"}))
        assert not fake_redis.has(_expense_key(1))

    def test_should_invalidate_cache_when_expense_deleted(
        self, repo, fake_redis, saved_expense
    ):
        repo.get_expense(1)
        repo.delete_expense(1)
        assert not fake_redis.has(_expense_key(1))
