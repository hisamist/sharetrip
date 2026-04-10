from pydantic import BaseModel


class TripRequest(BaseModel):
    name: str
    base_currency: str


class TripResponse(BaseModel):
    id: int
    name: str
    base_currency: str
