from fastapi import APIRouter, Depends, HTTPException, status

from sharetrip.api.dependencies import get_current_user, get_trip_repository
from sharetrip.api.schemas.trips import TripRequest, TripResponse
from sharetrip.domain.entities.membership import Membership
from sharetrip.domain.entities.trip import Trip
from sharetrip.domain.entities.user import User

router = APIRouter(prefix="/trips", tags=["Trips"])


@router.post("", response_model=TripResponse, status_code=201)
def create_trip(
    body: TripRequest,
    trip_repo=Depends(get_trip_repository),
    current_user: User = Depends(get_current_user),
):
    trip = trip_repo.save_trip(Trip(name=body.name, base_currency=body.base_currency))
    trip_repo.add_member(Membership(trip_id=trip.id, user_id=current_user.id))
    return TripResponse(id=trip.id, name=trip.name, base_currency=trip.base_currency)


@router.get("/{trip_id}", response_model=TripResponse)
def get_trip(
    trip_id: int,
    trip_repo=Depends(get_trip_repository),
    _: User = Depends(get_current_user),
):
    trip = trip_repo.get_trip(trip_id)
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        )
    return TripResponse(id=trip.id, name=trip.name, base_currency=trip.base_currency)


@router.post("/{trip_id}/members", status_code=204)
def add_member(
    trip_id: int,
    user_id: int,
    trip_repo=Depends(get_trip_repository),
    _: User = Depends(get_current_user),
):
    trip = trip_repo.get_trip(trip_id)
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        )
    trip_repo.add_member(Membership(trip_id=trip_id, user_id=user_id))
