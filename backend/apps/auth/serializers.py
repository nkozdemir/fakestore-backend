from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.users.validators import (
    validate_password as validate_password_rules,
    validate_username as validate_username_rules,
)


class RegisterRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField()
    last_name = serializers.CharField()

    def validate_username(self, value: str) -> str:
        return validate_username_rules(value)

    def validate_password(self, value: str) -> str:
        return validate_password_rules(value)


class RegisterResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()


class UsernameAvailabilityRequestSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=1)

    def validate_username(self, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise serializers.ValidationError("Username cannot be blank.")
        return trimmed


class UsernameAvailabilityResponseSerializer(serializers.Serializer):
    username = serializers.CharField()
    available = serializers.BooleanField()


class MeResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    last_login = serializers.DateTimeField(allow_null=True)
    date_joined = serializers.DateTimeField()
    is_staff = serializers.BooleanField()
    is_superuser = serializers.BooleanField()


class LogoutRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class DetailResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class CustomerTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Token serializer that blocks staff/admin accounts."""

    def validate(self, attrs):
        data = super().validate(attrs)
        if getattr(self.user, "is_staff", False) or getattr(
            self.user, "is_superuser", False
        ):
            raise ValidationError(
                "Staff and admin accounts must use the staff login endpoint."
            )
        return data


class StaffTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Token serializer that only allows staff or superusers."""

    def validate(self, attrs):
        data = super().validate(attrs)
        if not (
            getattr(self.user, "is_staff", False)
            or getattr(self.user, "is_superuser", False)
        ):
            raise ValidationError("Only staff or admin accounts may use this endpoint.")
        return data
