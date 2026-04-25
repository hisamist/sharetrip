import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sharetrip.domain.entities.expense import Expense, ExpenseSplit, SplitType
from sharetrip.domain.entities.membership import Membership, MemberRole
from sharetrip.domain.entities.trip import Trip, SettlementMethod, RoundingStrategy
from sharetrip.infrastructure.db.models import Base
from sharetrip.infrastructure.db.sql_trip_repository import SQLTripRepository


@pytest.fixture(scope="function")
def session():
    """Session SQLite en mémoire — isolée par test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(engine)
    engine.dispose()  # ferme toutes les connexions du pool


@pytest.fixture
def repo(session) -> SQLTripRepository:
    return SQLTripRepository(session)


@pytest.fixture
def saved_trip(repo) -> Trip:
    trip = Trip(name="Tokyo Trip", base_currency="EUR")
    return repo.save_trip(trip)


@pytest.fixture
def saved_expense(repo, saved_trip) -> Expense:
    expense = Expense(
        trip_id=saved_trip.id,
        paid_by=1,
        title="Resto",
        amount_pivot=90.0,
        split_type=SplitType.EQUAL,
    )
    return repo.save_expense(expense)


# ─── Trip CRUD ────────────────────────────────────────────────────────────────


class TestTripCRUD:
    def test_save_trip_assigns_id(self, repo):
        trip = repo.save_trip(Trip(name="Paris", base_currency="EUR"))
        assert trip.id is not None

    def test_get_trip_returns_correct_data(self, repo, saved_trip):
        fetched = repo.get_trip(saved_trip.id)
        assert fetched.name == "Tokyo Trip"
        assert fetched.base_currency == "EUR"
        assert fetched.settlement_method == SettlementMethod.MINIMIZE_TRANSFERS
        assert fetched.rounding_strategy == RoundingStrategy.ROUND_HALF_UP

    def test_get_trip_not_found_returns_none(self, repo):
        assert repo.get_trip(9999) is None

    def test_list_trips_returns_all(self, repo):
        repo.save_trip(Trip(name="Trip A", base_currency="EUR"))
        repo.save_trip(Trip(name="Trip B", base_currency="JPY"))
        trips = repo.list_trips()
        assert len(trips) == 2
        names = {t.name for t in trips}
        assert names == {"Trip A", "Trip B"}

    def test_save_trip_update(self, repo, saved_trip):
        updated = Trip(id=saved_trip.id, name="Updated", base_currency="USD")
        result = repo.save_trip(updated)
        assert result.name == "Updated"
        assert result.base_currency == "USD"

    def test_delete_trip(self, repo, saved_trip):
        repo.delete_trip(saved_trip.id)
        assert repo.get_trip(saved_trip.id) is None

    def test_delete_trip_not_found_raises(self, repo):
        with pytest.raises(ValueError, match="not found"):
            repo.delete_trip(9999)


# ─── Member CRUD ──────────────────────────────────────────────────────────────


class TestMemberCRUD:
    def test_add_member(self, repo, saved_trip):
        membership = Membership(trip_id=saved_trip.id, user_id=1, role=MemberRole.ADMIN)
        result = repo.add_member(membership)
        assert result.user_id == 1
        assert result.role == MemberRole.ADMIN

    def test_get_members(self, repo, saved_trip):
        repo.add_member(Membership(trip_id=saved_trip.id, user_id=1))
        repo.add_member(Membership(trip_id=saved_trip.id, user_id=2))
        members = repo.get_members(saved_trip.id)
        assert len(members) == 2
        assert {m.user_id for m in members} == {1, 2}

    def test_get_members_empty(self, repo, saved_trip):
        assert repo.get_members(saved_trip.id) == []

    def test_remove_member(self, repo, saved_trip):
        repo.add_member(Membership(trip_id=saved_trip.id, user_id=1))
        repo.remove_member(saved_trip.id, user_id=1)
        assert repo.get_members(saved_trip.id) == []

    def test_remove_member_not_found_raises(self, repo, saved_trip):
        with pytest.raises(ValueError, match="not found"):
            repo.remove_member(saved_trip.id, user_id=999)

    def test_weight_percentage_persisted(self, repo, saved_trip):
        repo.add_member(
            Membership(trip_id=saved_trip.id, user_id=1, weight_percentage=60.0)
        )
        members = repo.get_members(saved_trip.id)
        assert members[0].weight_percentage == 60.0


# ─── list_trips_for_user ──────────────────────────────────────────────────────


class TestListTripsForUser:
    def test_returns_only_trips_user_is_member_of(self, repo):
        trip_a = repo.save_trip(Trip(name="Trip A", base_currency="EUR"))
        trip_b = repo.save_trip(Trip(name="Trip B", base_currency="EUR"))
        repo.save_trip(Trip(name="Trip C", base_currency="EUR"))

        repo.add_member(Membership(trip_id=trip_a.id, user_id=1))
        repo.add_member(Membership(trip_id=trip_b.id, user_id=1))

        trips = repo.list_trips_for_user(1)
        assert len(trips) == 2
        assert {t.name for t in trips} == {"Trip A", "Trip B"}

    def test_returns_empty_when_user_has_no_memberships(self, repo):
        repo.save_trip(Trip(name="Some Trip", base_currency="EUR"))
        assert repo.list_trips_for_user(999) == []

    def test_does_not_return_trips_of_other_users(self, repo):
        trip = repo.save_trip(Trip(name="Alice Trip", base_currency="EUR"))
        repo.add_member(Membership(trip_id=trip.id, user_id=1))
        assert repo.list_trips_for_user(2) == []


# ─── Expense CRUD ─────────────────────────────────────────────────────────────


class TestExpenseCRUD:
    def test_save_expense_assigns_id(self, repo, saved_trip):
        expense = Expense(
            trip_id=saved_trip.id,
            paid_by=1,
            title="Hotel",
            amount_pivot=200.0,
            split_type=SplitType.EQUAL,
        )
        result = repo.save_expense(expense)
        assert result.id is not None

    def test_get_expense_returns_correct_data(self, repo, saved_expense):
        fetched = repo.get_expense(saved_expense.id)
        assert fetched.title == "Resto"
        assert fetched.amount_pivot == 90.0
        assert fetched.split_type == SplitType.EQUAL

    def test_get_expense_not_found_returns_none(self, repo):
        assert repo.get_expense(9999) is None

    def test_list_expenses_by_trip(self, repo, saved_trip):
        for title in ("Hotel", "Taxi", "Resto"):
            repo.save_expense(
                Expense(
                    trip_id=saved_trip.id,
                    paid_by=1,
                    title=title,
                    amount_pivot=50.0,
                    split_type=SplitType.EQUAL,
                )
            )
        expenses = repo.list_expenses(saved_trip.id)
        assert len(expenses) == 3

    def test_list_expenses_only_for_trip(self, repo, saved_trip):
        other_trip = repo.save_trip(Trip(name="Other", base_currency="USD"))
        repo.save_expense(
            Expense(
                trip_id=saved_trip.id,
                paid_by=1,
                title="Mine",
                amount_pivot=10.0,
                split_type=SplitType.EQUAL,
            )
        )
        repo.save_expense(
            Expense(
                trip_id=other_trip.id,
                paid_by=1,
                title="Other",
                amount_pivot=10.0,
                split_type=SplitType.EQUAL,
            )
        )
        assert len(repo.list_expenses(saved_trip.id)) == 1

    def test_delete_expense(self, repo, saved_expense):
        repo.delete_expense(saved_expense.id)
        assert repo.get_expense(saved_expense.id) is None

    def test_delete_expense_not_found_raises(self, repo):
        with pytest.raises(ValueError, match="not found"):
            repo.delete_expense(9999)

    def test_original_currency_and_rate_persisted(self, repo, saved_trip):
        expense = Expense(
            trip_id=saved_trip.id,
            paid_by=1,
            title="Sushi",
            amount_pivot=30.5,
            split_type=SplitType.EQUAL,
            original_currency="JPY",
            exchange_rate=0.0061,
        )
        saved = repo.save_expense(expense)
        fetched = repo.get_expense(saved.id)
        assert fetched.original_currency == "JPY"
        assert fetched.exchange_rate == pytest.approx(0.0061)


# ─── Splits ───────────────────────────────────────────────────────────────────


class TestSplits:
    def test_save_and_get_splits(self, repo, saved_expense):
        splits = [
            ExpenseSplit(
                expense_id=saved_expense.id,
                user_id=1,
                share_ratio=1.0,
                amount_owed=45.0,
            ),
            ExpenseSplit(
                expense_id=saved_expense.id,
                user_id=2,
                share_ratio=1.0,
                amount_owed=45.0,
            ),
        ]
        saved = repo.save_splits(splits)
        assert len(saved) == 2
        assert all(s.id is not None for s in saved)

    def test_get_splits_returns_correct_amounts(self, repo, saved_expense):
        repo.save_splits(
            [
                ExpenseSplit(
                    expense_id=saved_expense.id,
                    user_id=1,
                    share_ratio=2.0,
                    amount_owed=60.0,
                ),
                ExpenseSplit(
                    expense_id=saved_expense.id,
                    user_id=2,
                    share_ratio=1.0,
                    amount_owed=30.0,
                ),
            ]
        )
        fetched = repo.get_splits(saved_expense.id)
        amounts = {s.user_id: s.amount_owed for s in fetched}
        assert amounts[1] == pytest.approx(60.0)
        assert amounts[2] == pytest.approx(30.0)

    def test_get_splits_empty(self, repo, saved_expense):
        assert repo.get_splits(saved_expense.id) == []
