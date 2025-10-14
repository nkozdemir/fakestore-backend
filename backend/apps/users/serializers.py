from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from .dtos import UserDTO, AddressDTO
from .models import User


class AddressSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    street = serializers.CharField()
    number = serializers.IntegerField()
    city = serializers.CharField()
    zipcode = serializers.CharField()
    latitude = serializers.CharField()
    longitude = serializers.CharField()


class GeoSerializer(serializers.Serializer):
    lat = serializers.DecimalField(max_digits=10, decimal_places=6)
    long = serializers.DecimalField(max_digits=10, decimal_places=6)


class AddressWriteSerializer(serializers.Serializer):
    city = serializers.CharField()
    street = serializers.CharField()
    number = serializers.IntegerField()
    zipcode = serializers.CharField()
    geolocation = GeoSerializer()


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    username = serializers.CharField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    phone = serializers.CharField()
    addresses = AddressSerializer(many=True, read_only=True)
    first_name = serializers.CharField(
        required=False, allow_blank=True, write_only=True
    )
    last_name = serializers.CharField(required=False, allow_blank=True, write_only=True)
    password = serializers.CharField(write_only=True, required=False)
    address = AddressWriteSerializer(write_only=True, required=False)

    class _Name(serializers.Serializer):
        first_name = serializers.CharField(allow_blank=True)
        last_name = serializers.CharField(allow_blank=True)

    name = _Name(write_only=True, required=False)

    def to_representation(self, obj: UserDTO):
        data = super().to_representation(obj)
        data["name"] = {
            "first_name": self._extract_name(obj, "first_name"),
            "last_name": self._extract_name(obj, "last_name"),
        }
        return data

    def validate(self, attrs):
        name = attrs.pop("name", None)
        if name:
            attrs["first_name"] = name.get("first_name")
            attrs["last_name"] = name.get("last_name")
        if self.instance is None and not getattr(self, "partial", False):
            required_fields = [
                "email",
                "username",
                "phone",
                "password",
                "first_name",
                "last_name",
            ]
            missing = []
            for field in required_fields:
                value = attrs.get(field)
                if value is None or (isinstance(value, str) and not value.strip()):
                    missing.append(field)
            if missing:
                raise serializers.ValidationError(
                    {field: "This field is required." for field in missing}
                )
        return super().validate(attrs)

    @staticmethod
    def _extract_name(obj, attr: str):
        if isinstance(obj, dict):
            return obj.get(attr)
        return getattr(obj, attr, None)
