from dataclasses import dataclass
from typing import List, Optional
from .models import User, Address


@dataclass
class AddressDTO:
    id: int
    street: str
    number: int
    city: str
    zipcode: str
    latitude: str
    longitude: str


@dataclass
class UserDTO:
    id: int
    first_name: str
    last_name: str
    email: str
    username: str
    phone: str
    date_joined: Optional[str]
    addresses: List[AddressDTO]


def address_to_dto(a: Address) -> AddressDTO:
    return AddressDTO(
        id=a.id,
        street=a.street,
        number=a.number,
        city=a.city,
        zipcode=a.zipcode,
        latitude=str(a.latitude),
        longitude=str(a.longitude),
    )


def user_to_dto(u: User) -> UserDTO:
    joined = getattr(u, "date_joined", None)
    if joined is not None:
        try:
            joined = joined.isoformat()
        except AttributeError:
            joined = str(joined)
    return UserDTO(
        id=u.id,
        first_name=u.first_name,
        last_name=u.last_name,
        email=u.email,
        username=u.username,
        phone=u.phone,
        date_joined=joined,
        addresses=[address_to_dto(a) for a in u.addresses.all()],
    )
