from fastapi import APIRouter, Depends, HTTPException, status

from sharetrip.api.dependencies import (
    get_currency_port,
    get_current_user,
    get_trip_repository,
    require_trip_member,
)
from sharetrip.api.schemas.expenses import (
    AddExpenseRequest,
    ExpenseResponse,
    SplitResponse,
)
from sharetrip.domain.entities.expense import ExpenseSplit
from sharetrip.domain.entities.user import User
from sharetrip.domain.services.split_factory import SplitFactory
from sharetrip.infrastructure.notifications.log_observer import LogNotificationObserver
from sharetrip.use_cases.add_expense import AddExpenseInput, AddExpenseUseCase

router = APIRouter(prefix="/trips", tags=["Expenses"])


def _to_expense_response(expense, splits) -> ExpenseResponse:
    return ExpenseResponse(
        id=expense.id,
        trip_id=expense.trip_id,
        paid_by=expense.paid_by,
        title=expense.title,
        amount_pivot=expense.amount_pivot,
        original_currency=expense.original_currency,
        exchange_rate=expense.exchange_rate,
        split_type=expense.split_type,
        category=expense.category,
        splits=[
            SplitResponse(
                user_id=s.user_id,
                amount_owed=s.amount_owed,
                share_ratio=s.share_ratio,
            )
            for s in splits
        ],
    )


@router.post("/{trip_id}/expenses", response_model=ExpenseResponse, status_code=201)
def add_expense(
    body: AddExpenseRequest,
    trip=Depends(require_trip_member),
    trip_repo=Depends(get_trip_repository),
    currency_port=Depends(get_currency_port),
    current_user: User = Depends(get_current_user),
):
    splits = [
        ExpenseSplit(expense_id=None, user_id=s.user_id, share_ratio=s.share_ratio)
        for s in body.splits
    ]
    use_case = AddExpenseUseCase(
        trip_repository=trip_repo,
        currency_port=currency_port,
        split_factory=SplitFactory(),
        observers=[LogNotificationObserver()],
    )
    try:
        output = use_case.execute(
            AddExpenseInput(
                trip_id=trip.id,
                paid_by=current_user.id,
                title=body.title,
                amount=body.amount,
                currency=body.currency,
                split_type=body.split_type,
                category=body.category,
                splits=splits,
            )
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )

    return _to_expense_response(output.expense, output.splits)


@router.get("/{trip_id}/expenses", response_model=list[ExpenseResponse])
def list_expenses(
    trip=Depends(require_trip_member),
    trip_repo=Depends(get_trip_repository),
):
    expenses = trip_repo.list_expenses(trip.id)
    return [
        _to_expense_response(expense, trip_repo.get_splits(expense.id))
        for expense in expenses
    ]
