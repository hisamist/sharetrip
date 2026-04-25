import json

from sharetrip.domain.entities.expense import Expense, ExpenseSplit
from sharetrip.domain.entities.membership import Membership
from sharetrip.domain.entities.trip import Trip
from sharetrip.domain.interfaces.trip_repository import TripRepository
from sharetrip.infrastructure.cache.redis_port import RedisPort

_TTL = 300  # 5 minutes


def _trip_key(trip_id: int) -> str:
    return f"trip:{trip_id}"


def _members_key(trip_id: int) -> str:
    return f"trip:{trip_id}:members"


def _expense_key(expense_id: int) -> str:
    return f"expense:{expense_id}"


class CachedTripRepository(TripRepository):
    """Decorator sur TripRepository — ajoute une couche cache Redis.

    Stratégie :
      - get_trip / get_members / get_expense  → cache-aside (READ)
      - save / delete                         → délègue + invalide le cache (WRITE)
      - list_* / save_splits / get_splits     → toujours délégués (pas cachés)
    """

    def __init__(self, inner: TripRepository, redis: RedisPort) -> None:
        self._inner = inner
        self._redis = redis

    # ─── Trip ─────────────────────────────────────────────────────────────────

    def get_trip(self, trip_id: int) -> Trip | None:
        cached = self._redis.get(_trip_key(trip_id))
        if cached is not None:
            return Trip.model_validate_json(cached)

        trip = self._inner.get_trip(trip_id)
        if trip is not None:
            self._redis.set(_trip_key(trip_id), trip.model_dump_json(), ex=_TTL)
        return trip

    def list_trips(self) -> list[Trip]:
        return self._inner.list_trips()

    def list_trips_for_user(self, user_id: int) -> list[Trip]:
        return self._inner.list_trips_for_user(user_id)

    def save_trip(self, trip: Trip) -> Trip:
        saved = self._inner.save_trip(trip)
        self._redis.delete(_trip_key(saved.id))
        return saved

    def delete_trip(self, trip_id: int) -> None:
        self._inner.delete_trip(trip_id)
        self._redis.delete(
            _trip_key(trip_id),
            _members_key(trip_id),
        )

    # ─── Members ──────────────────────────────────────────────────────────────

    def get_members(self, trip_id: int) -> list[Membership]:
        cached = self._redis.get(_members_key(trip_id))
        if cached is not None:
            return [Membership.model_validate(m) for m in json.loads(cached)]

        members = self._inner.get_members(trip_id)
        payload = json.dumps([m.model_dump() for m in members])
        self._redis.set(_members_key(trip_id), payload, ex=_TTL)
        return members

    def add_member(self, membership: Membership) -> Membership:
        saved = self._inner.add_member(membership)
        self._redis.delete(_members_key(membership.trip_id))
        return saved

    def remove_member(self, trip_id: int, user_id: int) -> None:
        self._inner.remove_member(trip_id, user_id)
        self._redis.delete(_members_key(trip_id))

    # ─── Expense ──────────────────────────────────────────────────────────────

    def get_expense(self, expense_id: int) -> Expense | None:
        cached = self._redis.get(_expense_key(expense_id))
        if cached is not None:
            return Expense.model_validate_json(cached)

        expense = self._inner.get_expense(expense_id)
        if expense is not None:
            self._redis.set(_expense_key(expense_id), expense.model_dump_json(), ex=_TTL)
        return expense

    def list_expenses(self, trip_id: int) -> list[Expense]:
        return self._inner.list_expenses(trip_id)

    def save_expense(self, expense: Expense) -> Expense:
        saved = self._inner.save_expense(expense)
        if saved.id is not None:
            self._redis.delete(_expense_key(saved.id))
        return saved

    def delete_expense(self, expense_id: int) -> None:
        self._inner.delete_expense(expense_id)
        self._redis.delete(_expense_key(expense_id))

    # ─── Splits — pas mis en cache ────────────────────────────────────────────

    def save_splits(self, splits: list[ExpenseSplit]) -> list[ExpenseSplit]:
        return self._inner.save_splits(splits)

    def get_splits(self, expense_id: int) -> list[ExpenseSplit]:
        return self._inner.get_splits(expense_id)
