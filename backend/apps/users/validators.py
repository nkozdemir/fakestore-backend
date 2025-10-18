import re
import string

from rest_framework import serializers

_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9]+$")


def validate_username(value: str) -> str:
    """
    Ensures that the username is at least 4 characters long and only contains
    alphanumeric characters.
    """
    if value is None:
        raise serializers.ValidationError("Username is required.")
    trimmed = value.strip()
    if len(trimmed) < 4:
        raise serializers.ValidationError(
            "Username must be at least 4 characters long."
        )
    if not _USERNAME_PATTERN.match(trimmed):
        raise serializers.ValidationError(
            "Username may contain only letters and numbers."
        )
    return trimmed


def validate_password(value: str) -> str:
    """
    Ensures that the password meets the complexity requirements:
    - minimum length of 6 characters
    - at least one uppercase letter
    - at least one lowercase letter
    - at least one number
    - at least one special character
    """
    if value is None:
        raise serializers.ValidationError("Password is required.")
    if len(value) < 6:
        raise serializers.ValidationError(
            "Password must be at least 6 characters long."
        )

    if not any(ch.isupper() for ch in value):
        raise serializers.ValidationError(
            "Password must include at least one uppercase letter."
        )
    if not any(ch.islower() for ch in value):
        raise serializers.ValidationError(
            "Password must include at least one lowercase letter."
        )
    if not any(ch.isdigit() for ch in value):
        raise serializers.ValidationError(
            "Password must include at least one number."
        )
    if not any(ch in string.punctuation for ch in value):
        raise serializers.ValidationError(
            "Password must include at least one special character."
        )
    return value
