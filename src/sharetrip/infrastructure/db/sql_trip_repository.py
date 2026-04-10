from sqlalchemy.orm import Session

from sharetrip.domain.entities.expense import Expense, ExpenseSplit, SplitType
from sharetrip.domain.entities.membership import Membership, MemberRole
from sharetrip.domain.entities.trip import Trip, SettlementMethod, RoundingStrategy
from sharetrip.domain.interfaces.trip_repository import TripRepository
from sharetrip.infrastructure.db.models import (
    ExpenseORM,
    ExpenseSplitORM,
    MembershipORM,
    TripORM,
)


class SQLTripRepository(TripRepository):
    """Implémentation concrète de TripRepository via SQLAlchemy.

    Traduit les entités du domaine ↔ modèles ORM.
    Le domaine ne connaît jamais SQLAlchemy.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ─── Trip ─────────────────────────────────────────────────────────────────

    def get_trip(self, trip_id: int) -> Trip | None:
        row = self._session.get(TripORM, trip_id)
        if row is None:
            return None
        return self._trip_to_domain(row)

    def save_trip(self, trip: Trip) -> Trip:
        if trip.id is None:
            row = TripORM(
                name=trip.name,
                base_currency=trip.base_currency,
                settlement_method=trip.settlement_method,
                rounding_strategy=trip.rounding_strategy,
                budget_limit=trip.budget_limit,
            )
            self._session.add(row)
        else:
            row = self._session.get(TripORM, trip.id)
            if row is None:
                raise ValueError(f"Trip {trip.id} not found")
            row.name = trip.name
            row.base_currency = trip.base_currency
            row.settlement_method = trip.settlement_method
            row.rounding_strategy = trip.rounding_strategy
            row.budget_limit = trip.budget_limit

        self._session.flush()
        return self._trip_to_domain(row)

    def list_trips(self) -> list[Trip]:
        rows = self._session.query(TripORM).all()
        return [self._trip_to_domain(r) for r in rows]

    def delete_trip(self, trip_id: int) -> None:
        row = self._session.get(TripORM, trip_id)
        if row is None:
            raise ValueError(f"Trip {trip_id} not found")
        self._session.delete(row)
        self._session.flush()

    # ─── Members ──────────────────────────────────────────────────────────────

    def get_members(self, trip_id: int) -> list[Membership]:
        rows = (
            self._session.query(MembershipORM)
            .filter(MembershipORM.trip_id == trip_id)
            .all()
        )
        return [self._membership_to_domain(r) for r in rows]

    def add_member(self, membership: Membership) -> Membership:
        row = MembershipORM(
            trip_id=membership.trip_id,
            user_id=membership.user_id,
            role=membership.role,
            weight_percentage=membership.weight_percentage,
        )
        self._session.add(row)
        self._session.flush()
        return self._membership_to_domain(row)

    def remove_member(self, trip_id: int, user_id: int) -> None:
        row = (
            self._session.query(MembershipORM)
            .filter(
                MembershipORM.trip_id == trip_id,
                MembershipORM.user_id == user_id,
            )
            .first()
        )
        if row is None:
            raise ValueError(f"Member {user_id} not found in trip {trip_id}")
        self._session.delete(row)
        self._session.flush()

    # ─── Expense ──────────────────────────────────────────────────────────────

    def get_expense(self, expense_id: int) -> Expense | None:
        row = self._session.get(ExpenseORM, expense_id)
        if row is None:
            return None
        return self._expense_to_domain(row)

    def list_expenses(self, trip_id: int) -> list[Expense]:
        rows = (
            self._session.query(ExpenseORM).filter(ExpenseORM.trip_id == trip_id).all()
        )
        return [self._expense_to_domain(r) for r in rows]

    def delete_expense(self, expense_id: int) -> None:
        row = self._session.get(ExpenseORM, expense_id)
        if row is None:
            raise ValueError(f"Expense {expense_id} not found")
        self._session.delete(row)
        self._session.flush()

    def save_expense(self, expense: Expense) -> Expense:
        if expense.id is None:
            row = ExpenseORM(
                trip_id=expense.trip_id,
                paid_by=expense.paid_by,
                title=expense.title,
                amount_pivot=expense.amount_pivot,
                split_type=expense.split_type,
                category=expense.category,
                original_currency=expense.original_currency,
                exchange_rate=expense.exchange_rate,
            )
            self._session.add(row)
        else:
            row = self._session.get(ExpenseORM, expense.id)
            if row is None:
                raise ValueError(f"Expense {expense.id} not found")
            row.title = expense.title
            row.amount_pivot = expense.amount_pivot
            row.category = expense.category

        self._session.flush()
        return self._expense_to_domain(row)

    # ─── Splits ───────────────────────────────────────────────────────────────

    def save_splits(self, splits: list[ExpenseSplit]) -> list[ExpenseSplit]:
        rows = []
        for split in splits:
            row = ExpenseSplitORM(
                expense_id=split.expense_id,
                user_id=split.user_id,
                share_ratio=split.share_ratio,
                amount_owed=split.amount_owed,
            )
            self._session.add(row)
            rows.append(row)

        self._session.flush()
        return [self._split_to_domain(r) for r in rows]

    def get_splits(self, expense_id: int) -> list[ExpenseSplit]:
        rows = (
            self._session.query(ExpenseSplitORM)
            .filter(ExpenseSplitORM.expense_id == expense_id)
            .all()
        )
        return [self._split_to_domain(r) for r in rows]

    # ─── Mappers ORM → Domaine ────────────────────────────────────────────────

    @staticmethod
    def _trip_to_domain(row: TripORM) -> Trip:
        return Trip(
            id=row.id,
            name=row.name,
            base_currency=row.base_currency,
            settlement_method=SettlementMethod(row.settlement_method),
            rounding_strategy=RoundingStrategy(row.rounding_strategy),
            budget_limit=row.budget_limit,
        )

    @staticmethod
    def _membership_to_domain(row: MembershipORM) -> Membership:
        return Membership(
            trip_id=row.trip_id,
            user_id=row.user_id,
            role=MemberRole(row.role),
            weight_percentage=row.weight_percentage,
        )

    @staticmethod
    def _expense_to_domain(row: ExpenseORM) -> Expense:
        return Expense(
            id=row.id,
            trip_id=row.trip_id,
            paid_by=row.paid_by,
            title=row.title,
            amount_pivot=row.amount_pivot,
            split_type=SplitType(row.split_type),
            category=row.category,
            original_currency=row.original_currency,
            exchange_rate=row.exchange_rate,
            created_at=row.created_at,
        )

    @staticmethod
    def _split_to_domain(row: ExpenseSplitORM) -> ExpenseSplit:
        return ExpenseSplit(
            id=row.id,
            expense_id=row.expense_id,
            user_id=row.user_id,
            share_ratio=row.share_ratio,
            amount_owed=row.amount_owed,
        )
