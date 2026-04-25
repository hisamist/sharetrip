from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from sharetrip.api.dependencies import (
    get_current_user,
    get_trip_repository,
    get_user_repository,
    require_trip_member,
)
from sharetrip.api.schemas.trips import MemberResponse, TripRequest, TripResponse
from sharetrip.domain.entities.membership import Membership
from sharetrip.domain.entities.trip import Trip
from sharetrip.domain.entities.user import User

router = APIRouter(prefix="/trips", tags=["Trips"])


class AddMemberRequest(BaseModel):
    user_id: int


@router.get("", response_model=list[TripResponse])
def list_my_trips(
    trip_repo=Depends(get_trip_repository),
    current_user: User = Depends(get_current_user),
):
    trips = trip_repo.list_trips_for_user(current_user.id)
    return [
        TripResponse(id=t.id, name=t.name, base_currency=t.base_currency) for t in trips
    ]


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
    trip=Depends(require_trip_member),
):
    return TripResponse(id=trip.id, name=trip.name, base_currency=trip.base_currency)


@router.get("/{trip_id}/members", response_model=list[MemberResponse])
def list_members(
    trip=Depends(require_trip_member),
    trip_repo=Depends(get_trip_repository),
    user_repo=Depends(get_user_repository),
):
    members = trip_repo.get_members(trip.id)
    result = []
    for m in members:
        user = user_repo.get_by_id(m.user_id)
        result.append(
            MemberResponse(
                user_id=m.user_id,
                display_name=user.display_name if user else f"User #{m.user_id}",
                role=m.role,
            )
        )
    return result


@router.post("/{trip_id}/members", status_code=204)
def add_member(
    body: AddMemberRequest,
    trip=Depends(require_trip_member),
    trip_repo=Depends(get_trip_repository),
    user_repo=Depends(get_user_repository),
):
    user = user_repo.get_by_id(body.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    members = trip_repo.get_members(trip.id)
    if any(m.user_id == body.user_id for m in members):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User is already a member"
        )

    trip_repo.add_member(Membership(trip_id=trip.id, user_id=body.user_id))
