from abc import ABC, abstractmethod

from sharetrip.domain.entities.expense import Expense, ExpenseSplit
from sharetrip.domain.entities.membership import Membership


class SplitStrategy(ABC):
    @abstractmethod
    def calculate(self, expense: Expense, members: list[Membership]) -> list[ExpenseSplit]:
        """Calcule et retourne les ExpenseSplit avec amount_owed rempli."""
        ...


class EqualSplitter(SplitStrategy):
    """Divise le montant également entre tous les membres du trip."""

    def calculate(self, expense: Expense, members: list[Membership]) -> list[ExpenseSplit]:
        if not members:
            raise ValueError("Cannot split expense with no members")

        share = expense.amount_pivot / len(members)
        splits = []
        assigned = 0.0

        for i, m in enumerate(members):
            if i == len(members) - 1:
                amount_owed = round(expense.amount_pivot - assigned, 2)
            else:
                amount_owed = round(share, 2)
                assigned += amount_owed
            splits.append(
                ExpenseSplit(
                    expense_id=expense.id,
                    user_id=m.user_id,
                    share_ratio=1.0,
                    amount_owed=amount_owed,
                )
            )

        return splits


class PercentageSplitter(SplitStrategy):
    """Divise selon weight_percentage défini dans chaque Membership."""

    def calculate(self, expense: Expense, members: list[Membership]) -> list[ExpenseSplit]:
        if not members:
            raise ValueError("Cannot split expense with no members")

        total_weight = sum(m.weight_percentage for m in members)
        splits = []
        assigned = 0.0

        for i, m in enumerate(members):
            if i == len(members) - 1:
                amount_owed = round(expense.amount_pivot - assigned, 2)
            else:
                amount_owed = round(
                    expense.amount_pivot * (m.weight_percentage / total_weight), 2
                )
                assigned += amount_owed
            splits.append(
                ExpenseSplit(
                    expense_id=expense.id,
                    user_id=m.user_id,
                    share_ratio=m.weight_percentage,
                    amount_owed=amount_owed,
                )
            )

        return splits


class HybridSplitter(SplitStrategy):
    """Divise selon share_ratio déclaré sur chaque ExpenseSplit.

    Seuls les membres ayant un ExpenseSplit participent.
    Les autres ne doivent rien.
    """

    def calculate(self, expense: Expense, members: list[Membership]) -> list[ExpenseSplit]:
        if not expense.splits:
            raise ValueError("Hybrid split requires ExpenseSplits with share_ratio")

        total_shares = sum(s.share_ratio for s in expense.splits)
        splits = []
        assigned = 0.0

        for i, s in enumerate(expense.splits):
            if i == len(expense.splits) - 1:
                amount_owed = round(expense.amount_pivot - assigned, 2)
            else:
                amount_owed = round(
                    expense.amount_pivot * (s.share_ratio / total_shares), 2
                )
                assigned += amount_owed
            splits.append(
                ExpenseSplit(
                    expense_id=expense.id,
                    user_id=s.user_id,
                    share_ratio=s.share_ratio,
                    amount_owed=amount_owed,
                )
            )

        return splits
