from dataclasses import dataclass, field

from sharetrip.domain.entities.expense import Expense, ExpenseSplit, SplitType
from sharetrip.domain.interfaces.currency_port import CurrencyPort
from sharetrip.domain.interfaces.trip_repository import TripRepository
from sharetrip.domain.services.split_factory import SplitFactory


@dataclass
class AddExpenseInput:
    trip_id: int
    paid_by: int
    title: str
    amount: float
    currency: str
    split_type: SplitType
    category: str | None = None
    splits: list[ExpenseSplit] = field(default_factory=list)


@dataclass
class AddExpenseOutput:
    expense: Expense
    splits: list[ExpenseSplit]


class AddExpenseUseCase:
    def __init__(
        self,
        trip_repository: TripRepository,
        currency_port: CurrencyPort,
        split_factory: SplitFactory,
    ) -> None:
        self._repo = trip_repository
        self._currency = currency_port
        self._factory = split_factory

    def execute(self, input: AddExpenseInput) -> AddExpenseOutput:
        # 1. Récupérer le trip → connaître la devise pivot
        trip = self._repo.get_trip(input.trip_id)
        if trip is None:
            raise ValueError(f"Trip {input.trip_id} not found")

        members = self._repo.get_members(input.trip_id)
        if not members:
            raise ValueError(f"Trip {input.trip_id} has no members")

        # 2. Convertir le montant vers la devise pivot du trip
        rate = self._currency.get_rate(input.currency, trip.base_currency)
        amount_pivot = round(input.amount * rate, 2)

        # 3. Construire et persister l'Expense
        expense = Expense(
            trip_id=input.trip_id,
            paid_by=input.paid_by,
            title=input.title,
            amount_pivot=amount_pivot,
            split_type=input.split_type,
            category=input.category,
            original_currency=input.currency,
            exchange_rate=rate,
            splits=input.splits,
        )
        saved_expense = self._repo.save_expense(expense)

        # 4. Calculer les splits via la stratégie appropriée
        strategy = self._factory.get_strategy(input.split_type)
        splits = strategy.calculate(saved_expense, members)

        # 5. Persister les splits
        saved_splits = self._repo.save_splits(splits)

        return AddExpenseOutput(expense=saved_expense, splits=saved_splits)
