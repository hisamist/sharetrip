import logging

from sharetrip.domain.entities.expense import Expense
from sharetrip.domain.entities.trip import Trip
from sharetrip.domain.interfaces.expense_observer import ExpenseObserver

logger = logging.getLogger(__name__)


class LogNotificationObserver(ExpenseObserver):
    """Observer that logs expense events — ready to swap for email/push later."""

    def on_expense_created(self, expense: Expense, trip: Trip) -> None:
        remaining = None
        if trip.budget_limit is not None:
            remaining = trip.budget_limit - expense.amount_pivot
            if remaining < 0:
                logger.warning(
                    "Budget exceeded for trip %d (%s): limit=%.2f, expense=%.2f",
                    trip.id,
                    trip.name,
                    trip.budget_limit,
                    expense.amount_pivot,
                )
            else:
                logger.info(
                    "Expense added to trip %d (%s): %.2f %s — budget remaining: %.2f",
                    trip.id,
                    trip.name,
                    expense.amount_pivot,
                    trip.base_currency,
                    remaining,
                )
        else:
            logger.info(
                "Expense added to trip %d (%s): %.2f %s (paid by user %d)",
                trip.id,
                trip.name,
                expense.amount_pivot,
                trip.base_currency,
                expense.paid_by,
            )
