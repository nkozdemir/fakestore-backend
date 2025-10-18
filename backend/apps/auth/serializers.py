from rest_framework import serializers

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
    is_staff = serializers.BooleanField()
    is_superuser = serializers.BooleanField()


class LogoutRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class DetailResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
