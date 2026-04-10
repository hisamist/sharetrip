from fastapi import APIRouter, Depends, HTTPException, status

from sharetrip.api.dependencies import get_current_user, get_trip_repository
from sharetrip.api.schemas.expenses import TransferResponse
from sharetrip.domain.entities.user import User
from sharetrip.use_cases.compute_settlements import (
    ComputeSettlementsInput,
    ComputeSettlementsUseCase,
)

router = APIRouter(prefix="/trips", tags=["Settlements"])


@router.get("/{trip_id}/settlements", response_model=list[TransferResponse])
def get_settlements(
    trip_id: int,
    trip_repo=Depends(get_trip_repository),
    _: User = Depends(get_current_user),
):
    try:
        output = ComputeSettlementsUseCase(trip_repo).execute(
            ComputeSettlementsInput(trip_id=trip_id)
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return [
        TransferResponse(
            from_user_id=t.from_user_id,
            to_user_id=t.to_user_id,
            amount=t.amount,
        )
        for t in output.transfers
    ]
