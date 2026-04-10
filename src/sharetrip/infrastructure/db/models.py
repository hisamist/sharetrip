from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)

    memberships: Mapped[list["MembershipORM"]] = relationship(back_populates="user")


class TripORM(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    settlement_method: Mapped[str] = mapped_column(String, nullable=False)
    rounding_strategy: Mapped[str] = mapped_column(String, nullable=False)
    budget_limit: Mapped[float | None] = mapped_column(Float, nullable=True)

    memberships: Mapped[list["MembershipORM"]] = relationship(back_populates="trip")
    expenses: Mapped[list["ExpenseORM"]] = relationship(back_populates="trip")


class MembershipORM(Base):
    __tablename__ = "memberships"

    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String, nullable=False, default="member")
    weight_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    trip: Mapped["TripORM"] = relationship(back_populates="memberships")
    user: Mapped["UserORM"] = relationship(back_populates="memberships")


class ExpenseORM(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False)
    paid_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    amount_pivot: Mapped[float] = mapped_column(Float, nullable=False)
    original_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    exchange_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    split_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    trip: Mapped["TripORM"] = relationship(back_populates="expenses")
    splits: Mapped[list["ExpenseSplitORM"]] = relationship(back_populates="expense")


class ExpenseSplitORM(Base):
    __tablename__ = "expense_splits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    share_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    amount_owed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    expense: Mapped["ExpenseORM"] = relationship(back_populates="splits")
