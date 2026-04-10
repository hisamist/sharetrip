from abc import ABC, abstractmethod

from sharetrip.domain.entities.expense import Expense, ExpenseSplit
from sharetrip.domain.entities.membership import Membership


class SplitStrategy(ABC):
    @abstractmethod
    def calculate(
        self, expense: Expense, members: list[Membership]
    ) -> list[ExpenseSplit]:
        """Calcule et retourne les ExpenseSplit avec amount_owed rempli."""
        ...


class EqualSplitter(SplitStrategy):
    """Divise le montant également entre tous les membres du trip."""

    def calculate(
        self, expense: Expense, members: list[Membership]
    ) -> list[ExpenseSplit]:
        if not members:
            raise ValueError("Cannot split expense with no members")

        share = expense.amount_pivot / len(members)

        return [
            ExpenseSplit(
                expense_id=expense.id,
                user_id=m.user_id,
                share_ratio=1.0,
                amount_owed=round(share, 2),
            )
            for m in members
        ]


class PercentageSplitter(SplitStrategy):
    """Divise selon weight_percentage défini dans chaque Membership."""

    def calculate(
        self, expense: Expense, members: list[Membership]
    ) -> list[ExpenseSplit]:
        if not members:
            raise ValueError("Cannot split expense with no members")

        total_weight = sum(m.weight_percentage for m in members)

        return [
            ExpenseSplit(
                expense_id=expense.id,
                user_id=m.user_id,
                share_ratio=m.weight_percentage,
                amount_owed=round(
                    expense.amount_pivot * (m.weight_percentage / total_weight), 2
                ),
            )
            for m in members
        ]


class HybridSplitter(SplitStrategy):
    """Divise selon share_ratio déclaré sur chaque ExpenseSplit.

    Seuls les membres ayant un ExpenseSplit participent.
    Les autres ne doivent rien.
    """

    def calculate(
        self, expense: Expense, members: list[Membership]
    ) -> list[ExpenseSplit]:
        if not expense.splits:
            raise ValueError("Hybrid split requires ExpenseSplits with share_ratio")

        total_shares = sum(s.share_ratio for s in expense.splits)

        return [
            ExpenseSplit(
                expense_id=expense.id,
                user_id=s.user_id,
                share_ratio=s.share_ratio,
                amount_owed=round(
                    expense.amount_pivot * (s.share_ratio / total_shares), 2
                ),
            )
            for s in expense.splits
        ]
