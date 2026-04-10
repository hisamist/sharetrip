import pytest

from sharetrip.domain.entities.expense import Expense, ExpenseSplit, SplitType
from sharetrip.domain.entities.membership import Membership
from sharetrip.domain.services.split_factory import SplitFactory
from sharetrip.domain.services.split_strategy import (
    EqualSplitter,
    HybridSplitter,
    PercentageSplitter,
)


@pytest.fixture
def factory() -> SplitFactory:
    return SplitFactory()


@pytest.fixture
def three_members() -> list[Membership]:
    return [Membership(trip_id=1, user_id=i) for i in range(1, 4)]


@pytest.fixture
def base_expense() -> Expense:
    return Expense(
        trip_id=1,
        paid_by=1,
        title="Resto",
        amount_pivot=90.0,
        split_type=SplitType.EQUAL,
    )


# ─── EqualSplitter ────────────────────────────────────────────────────────────


class TestEqualSplitter:
    def test_splits_evenly(self, base_expense, three_members):
        splits = EqualSplitter().calculate(base_expense, three_members)
        assert len(splits) == 3
        assert all(s.amount_owed == 30.0 for s in splits)

    def test_sum_equals_total(self, base_expense, three_members):
        splits = EqualSplitter().calculate(base_expense, three_members)
        assert sum(s.amount_owed for s in splits) == pytest.approx(90.0)

    def test_two_members(self, base_expense):
        members = [Membership(trip_id=1, user_id=i) for i in range(1, 3)]
        splits = EqualSplitter().calculate(base_expense, members)
        assert all(s.amount_owed == 45.0 for s in splits)

    def test_no_members_raises(self, base_expense):
        with pytest.raises(ValueError, match="no members"):
            EqualSplitter().calculate(base_expense, [])

    def test_share_ratio_is_one(self, base_expense, three_members):
        splits = EqualSplitter().calculate(base_expense, three_members)
        assert all(s.share_ratio == 1.0 for s in splits)


# ─── PercentageSplitter ───────────────────────────────────────────────────────


class TestPercentageSplitter:
    def test_60_40_split(self, base_expense):
        members = [
            Membership(trip_id=1, user_id=1, weight_percentage=60),
            Membership(trip_id=1, user_id=2, weight_percentage=40),
        ]
        splits = PercentageSplitter().calculate(base_expense, members)
        assert splits[0].amount_owed == pytest.approx(54.0)
        assert splits[1].amount_owed == pytest.approx(36.0)

    def test_sum_equals_total(self, base_expense):
        members = [
            Membership(trip_id=1, user_id=1, weight_percentage=60),
            Membership(trip_id=1, user_id=2, weight_percentage=40),
        ]
        splits = PercentageSplitter().calculate(base_expense, members)
        assert sum(s.amount_owed for s in splits) == pytest.approx(90.0)

    def test_equal_weights_behaves_like_equal_split(self, base_expense, three_members):
        splits = PercentageSplitter().calculate(base_expense, three_members)
        assert all(s.amount_owed == pytest.approx(30.0) for s in splits)

    def test_no_members_raises(self, base_expense):
        with pytest.raises(ValueError, match="no members"):
            PercentageSplitter().calculate(base_expense, [])


# ─── HybridSplitter ───────────────────────────────────────────────────────────


class TestHybridSplitter:
    def test_2_to_1_ratio(self, three_members):
        expense = Expense(
            trip_id=1,
            paid_by=1,
            title="Resto",
            amount_pivot=90.0,
            split_type=SplitType.HYBRID,
            splits=[
                ExpenseSplit(expense_id=None, user_id=1, share_ratio=2.0),
                ExpenseSplit(expense_id=None, user_id=2, share_ratio=1.0),
            ],
        )
        splits = HybridSplitter().calculate(expense, three_members)
        assert splits[0].amount_owed == pytest.approx(60.0)
        assert splits[1].amount_owed == pytest.approx(30.0)

    def test_only_participants_included(self, three_members):
        expense = Expense(
            trip_id=1,
            paid_by=1,
            title="Resto",
            amount_pivot=90.0,
            split_type=SplitType.HYBRID,
            splits=[
                ExpenseSplit(expense_id=None, user_id=1, share_ratio=1.0),
                ExpenseSplit(expense_id=None, user_id=2, share_ratio=1.0),
            ],
        )
        splits = HybridSplitter().calculate(expense, three_members)
        assert len(splits) == 2
        user_ids = {s.user_id for s in splits}
        assert 3 not in user_ids

    def test_sum_equals_total(self, three_members):
        expense = Expense(
            trip_id=1,
            paid_by=1,
            title="Resto",
            amount_pivot=90.0,
            split_type=SplitType.HYBRID,
            splits=[
                ExpenseSplit(expense_id=None, user_id=1, share_ratio=2.0),
                ExpenseSplit(expense_id=None, user_id=2, share_ratio=1.0),
            ],
        )
        splits = HybridSplitter().calculate(expense, three_members)
        assert sum(s.amount_owed for s in splits) == pytest.approx(90.0)

    def test_no_splits_raises(self, three_members):
        with pytest.raises(ValueError, match="share_ratio"):
            expense = Expense(
                trip_id=1,
                paid_by=1,
                title="Resto",
                amount_pivot=90.0,
                split_type=SplitType.EQUAL,
            )
            HybridSplitter().calculate(expense, three_members)


# ─── SplitFactory ─────────────────────────────────────────────────────────────


class TestSplitFactory:
    def test_returns_equal_splitter(self, factory):
        assert isinstance(factory.get_strategy(SplitType.EQUAL), EqualSplitter)

    def test_returns_percentage_splitter(self, factory):
        assert isinstance(
            factory.get_strategy(SplitType.PERCENTAGE), PercentageSplitter
        )

    def test_returns_hybrid_splitter(self, factory):
        assert isinstance(factory.get_strategy(SplitType.HYBRID), HybridSplitter)
