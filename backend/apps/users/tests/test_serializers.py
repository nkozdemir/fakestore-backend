from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError

from apps.users.serializers import AddressWriteSerializer


def test_address_write_serializer_rejects_non_numeric_geolocation():
    serializer = AddressWriteSerializer(
        data={
            "city": "Town",
            "street": "Main",
            "number": 10,
            "zipcode": "12345",
            "geolocation": {"lat": "north", "long": "east"},
        }
    )
    with pytest.raises(ValidationError):
        serializer.is_valid(raise_exception=True)


def test_address_write_serializer_accepts_decimal_geolocation():
    serializer = AddressWriteSerializer(
        data={
            "city": "Town",
            "street": "Main",
            "number": 10,
            "zipcode": "12345",
            "geolocation": {"lat": "12.345600", "long": "-98.765400"},
        }
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["geolocation"]["lat"] == Decimal("12.345600")
    assert serializer.validated_data["geolocation"]["long"] == Decimal("-98.765400")
