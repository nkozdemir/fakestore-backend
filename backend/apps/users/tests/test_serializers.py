from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError

from apps.users.serializers import AddressWriteSerializer, UserSerializer


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


def test_user_serializer_rejects_short_username():
    serializer = UserSerializer(
        data={
            "email": "short@example.com",
            "username": "abc",
            "phone": "1234567890",
            "password": "Valid1!",
            "first_name": "Jane",
            "last_name": "Doe",
        }
    )
    serializer.fields["username"].validators = []
    serializer.fields["email"].validators = []
    with pytest.raises(ValidationError) as exc:
        serializer.is_valid(raise_exception=True)
    assert "Username must be at least 4 characters long." in str(exc.value)


def test_user_serializer_rejects_password_missing_special_character():
    serializer = UserSerializer(
        data={
            "email": "strong@example.com",
            "username": "stronguser",
            "phone": "1234567890",
            "password": "NoSpecial1",
            "first_name": "Jane",
            "last_name": "Doe",
        }
    )
    serializer.fields["username"].validators = []
    serializer.fields["email"].validators = []
    with pytest.raises(ValidationError) as exc:
        serializer.is_valid(raise_exception=True)
    assert "Password must include at least one special character." in str(exc.value)
