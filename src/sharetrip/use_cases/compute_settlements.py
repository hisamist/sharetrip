from dataclasses import dataclass

from sharetrip.domain.interfaces.trip_repository import TripRepository


@dataclass
class Transfer:
    from_user_id: int
    to_user_id: int
    amount: float


@dataclass
class ComputeSettlementsInput:
    trip_id: int


@dataclass
class ComputeSettlementsOutput:
    transfers: list[Transfer]


class ComputeSettlementsUseCase:
    def __init__(self, trip_repository: TripRepository) -> None:
        self._repo = trip_repository

    def execute(self, input: ComputeSettlementsInput) -> ComputeSettlementsOutput:
        trip = self._repo.get_trip(input.trip_id)
        if trip is None:
            raise ValueError(f"Trip {input.trip_id} not found")

        # 1. Compute net balance per user
        #    balance > 0 → others owe them
        #    balance < 0 → they owe others
        balances: dict[int, float] = {}

        expenses = self._repo.list_expenses(input.trip_id)
        for expense in expenses:
            # payer is credited the full pivot amount
            balances[expense.paid_by] = (
                balances.get(expense.paid_by, 0.0) + expense.amount_pivot
            )

            splits = self._repo.get_splits(expense.id)
            for split in splits:
                balances[split.user_id] = (
                    balances.get(split.user_id, 0.0) - split.amount_owed
                )

        # 2. Minimize transfers (greedy)
        creditors = sorted(
            [(uid, bal) for uid, bal in balances.items() if bal > 0.001],
            key=lambda x: -x[1],
        )
        debtors = sorted(
            [(uid, -bal) for uid, bal in balances.items() if bal < -0.001],
            key=lambda x: -x[1],
        )

        transfers: list[Transfer] = []
        i, j = 0, 0
        while i < len(creditors) and j < len(debtors):
            cred_id, cred_amt = creditors[i]
            debt_id, debt_amt = debtors[j]

            settled = round(min(cred_amt, debt_amt), 2)
            transfers.append(
                Transfer(from_user_id=debt_id, to_user_id=cred_id, amount=settled)
            )

            cred_amt -= settled
            debt_amt -= settled

            if cred_amt < 0.001:
                i += 1
            else:
                creditors[i] = (cred_id, cred_amt)

            if debt_amt < 0.001:
                j += 1
            else:
                debtors[j] = (debt_id, debt_amt)

        return ComputeSettlementsOutput(transfers=transfers)
