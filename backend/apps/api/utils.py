from collections.abc import Mapping
from typing import Any, Dict, Optional

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.serializers import as_serializer_error

DEFAULT_ERROR_STATUS = status.HTTP_400_BAD_REQUEST

ERROR_STATUS_MAP = {
    "NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "VALIDATION_ERROR": status.HTTP_400_BAD_REQUEST,
    "UNAUTHORIZED": status.HTTP_401_UNAUTHORIZED,
    "SERVER_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
    "FORBIDDEN": status.HTTP_403_FORBIDDEN,
    "METHOD_NOT_ALLOWED": status.HTTP_405_METHOD_NOT_ALLOWED,
    "CONFLICT": status.HTTP_409_CONFLICT,
    "UNPROCESSABLE_ENTITY": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "TOO_MANY_REQUESTS": status.HTTP_429_TOO_MANY_REQUESTS,
    "SERVICE_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
}


def _normalize_details(details: Any) -> Any:
    if isinstance(details, ValidationError):
        return as_serializer_error(details)
    if isinstance(details, Mapping):
        return dict(details)
    if isinstance(details, Exception):
        return {"type": details.__class__.__name__}
    return details


def error_response(
    code: str,
    message: str,
    details: Optional[Any] = None,
    http_status: Optional[int] = None,
    *,
    hint: Optional[str] = None,
    extra: Optional[Mapping[str, Any]] = None,
    headers: Optional[Mapping[str, str]] = None,
) -> Response:
    """
    Return a consistently structured error response for API endpoints.

    Args:
        code: Machine-readable error identifier.
        message: Human-readable explanation of the error.
        details: Optional context, e.g. validation errors or exception details.
        http_status: Explicit HTTP status code to override the default mapping.
        hint: Optional actionable message for clients on how to resolve the error.
        extra: Optional mapping holding additional machine-readable fields.
        headers: Optional response headers to include alongside the payload.
    """

    if not isinstance(code, str):
        raise TypeError("error_response requires code to be a string")
    if not isinstance(message, str):
        raise TypeError("error_response requires message to be a string")

    code = code.strip()
    message = message.strip()

    if not code:
        raise ValueError("error_response requires a non-empty code")
    if not message:
        raise ValueError("error_response requires a non-empty message")

    normalized_code = code.upper()

    status_code = (
        int(http_status)
        if http_status is not None
        else ERROR_STATUS_MAP.get(normalized_code, DEFAULT_ERROR_STATUS)
    )

    if extra is not None and not isinstance(extra, Mapping):
        raise TypeError("error_response extra must be a mapping if provided")
    if headers is not None and not isinstance(headers, Mapping):
        raise TypeError("error_response headers must be a mapping if provided")
    if hint is not None and not isinstance(hint, str):
        raise TypeError("error_response hint must be a string if provided")

    if not 100 <= status_code <= 599:
        raise ValueError("error_response status must be a valid HTTP status code")

    payload: Dict[str, Any] = {
        "error": {
            "code": normalized_code,
            "message": message,
            "status": status_code,
        }
    }
    if details is not None:
        payload["error"]["details"] = _normalize_details(details)
    if hint is not None:
        payload["error"]["hint"] = hint
    if extra:
        payload["error"]["extra"] = dict(extra)

    headers_dict = (
        {str(key): str(value) for key, value in headers.items()} if headers else None
    )

    return Response(payload, status=status_code, headers=headers_dict)
