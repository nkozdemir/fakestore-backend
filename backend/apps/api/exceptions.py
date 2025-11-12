from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple, Union

from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
    ValidationError as DjangoValidationError,
)
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.api.utils import error_response
from apps.common import get_logger

logger = get_logger(__name__).bind(component="api", layer="exception")

STATUS_CODE_DEFAULTS: Dict[int, Tuple[str, str]] = {
    status.HTTP_400_BAD_REQUEST: ("VALIDATION_ERROR", _("Validation failed")),
    status.HTTP_401_UNAUTHORIZED: ("UNAUTHORIZED", _("Authentication required")),
    status.HTTP_403_FORBIDDEN: (
        "FORBIDDEN",
        _("You do not have permission to perform this action"),
    ),
    status.HTTP_404_NOT_FOUND: ("NOT_FOUND", _("Resource not found")),
    status.HTTP_405_METHOD_NOT_ALLOWED: ("METHOD_NOT_ALLOWED", _("Method not allowed")),
    status.HTTP_409_CONFLICT: ("CONFLICT", _("Resource conflict")),
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: (
        "UNSUPPORTED_MEDIA_TYPE",
        _("Unsupported media type"),
    ),
    status.HTTP_422_UNPROCESSABLE_ENTITY: (
        "UNPROCESSABLE_ENTITY",
        _("Unprocessable entity"),
    ),
    status.HTTP_429_TOO_MANY_REQUESTS: ("TOO_MANY_REQUESTS", _("Request was throttled")),
    status.HTTP_500_INTERNAL_SERVER_ERROR: (
        "SERVER_ERROR",
        _("Something went wrong"),
    ),
    status.HTTP_503_SERVICE_UNAVAILABLE: (
        "SERVICE_UNAVAILABLE",
        _("Service temporarily unavailable"),
    ),
}


class ApplicationError(Exception):
    """
    Domain-level application error meant to be raised from services or views.

    Args:
        code: Machine readable error code.
        message: Human readable explanation of the error.
        status_code: Optional explicit HTTP status. If omitted, code mapping is used.
        details: Optional structured details for clients.
        hint: Optional hint for remediation.
        extra: Optional additional machine readable fields.
        headers: Optional mapping of headers to include in the response.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: Optional[int] = None,
        details: Optional[Any] = None,
        hint: Optional[str] = None,
        extra: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        self.hint = hint
        self.extra = extra
        self.headers = headers

    def to_response(self) -> Response:
        return error_response(
            self.code,
            self.message,
            self.details,
            http_status=self.status_code,
            hint=self.hint,
            extra=self.extra,
            headers=self.headers,
        )


def global_exception_handler(exc: Exception, context: Dict[str, Any]) -> Response:
    """
    Central exception handler for DRF views returning structured JSON errors.
    """

    bound_logger = _bind_logger(context)

    if isinstance(exc, ApplicationError):
        bound_logger.info(
            "Handled application error",
            code=exc.code,
            status=exc.status_code,
        )
        return exc.to_response()

    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(_normalize_django_validation_error(exc))

    response = drf_exception_handler(exc, context)
    if response is not None:
        return _from_drf_exception(exc, response, bound_logger)

    bound_logger.exception("Unhandled exception bubbled to global handler")
    return error_response(
        "SERVER_ERROR",
        "Something went wrong",
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _bind_logger(context: Dict[str, Any]):
    log = logger
    view = context.get("view")
    request = context.get("request")
    if view:
        view_name = getattr(view, "__class__", type(view)).__name__
        log = log.bind(view=view_name)
    if request is not None:
        log = log.bind(
            method=getattr(request, "method", None),
            path=getattr(request, "path", None),
        )
    return log


def _from_drf_exception(
    exc: Exception, response: Response, bound_logger
) -> Response:
    status_code = response.status_code
    payload = response.data
    code, message, details, hint = _normalize_payload(exc, payload, status_code)
    headers = dict(response.headers) if getattr(response, "headers", None) else None

    if status_code >= 500:
        bound_logger.error(
            "Converted server error",
            code=code,
            status=status_code,
        )
    else:
        bound_logger.info("Converted API exception", code=code, status=status_code)

    return error_response(
        code,
        message,
        details,
        http_status=status_code,
        hint=hint,
        headers=headers,
    )


def _normalize_django_validation_error(
    exc: DjangoValidationError,
) -> Union[Dict[str, Any], list[str]]:
    if hasattr(exc, "message_dict"):
        return exc.message_dict
    if hasattr(exc, "messages"):
        return list(exc.messages)
    return {"detail": getattr(exc, "message", "Validation failed")}


def _normalize_payload(
    exc: Exception,
    payload: Any,
    status_code: int,
) -> Tuple[str, str, Optional[Any], Optional[str]]:
    if isinstance(exc, ValidationError):
        return (
            "VALIDATION_ERROR",
            _extract_message(payload, "Validation failed", status_code),
            payload,
            None,
        )
    if isinstance(exc, ParseError):
        return (
            "VALIDATION_ERROR",
            _extract_message(payload, "Malformed request", status_code),
            payload,
            None,
        )
    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        message = _extract_message(
            payload,
            "Authentication failed"
            if isinstance(exc, AuthenticationFailed)
            else "Authentication required",
            status_code,
        )
        return ("UNAUTHORIZED", message, None, None)
    if isinstance(exc, (PermissionDenied, DjangoPermissionDenied)):
        return (
            "FORBIDDEN",
            _extract_message(
                payload, "You do not have permission to perform this action", status_code
            ),
            None,
            None,
        )
    if isinstance(exc, (NotFound, Http404)):
        return (
            "NOT_FOUND",
            _extract_message(payload, "Resource not found", status_code),
            None,
            None,
        )
    if isinstance(exc, MethodNotAllowed):
        details = {"allowedMethods": list(getattr(exc, "allowed_methods", []))} or None
        return (
            "METHOD_NOT_ALLOWED",
            _extract_message(payload, "Method not allowed", status_code),
            details,
            None,
        )
    if isinstance(exc, Throttled):
        wait = getattr(exc, "wait", None)
        details = {"retryAfter": wait} if wait is not None else None
        hint = (
            "Wait before retrying this request."
            if wait is not None
            else None
        )
        return (
            "TOO_MANY_REQUESTS",
            _extract_message(payload, "Request was throttled", status_code),
            details,
            hint,
        )

    code, default_message = STATUS_CODE_DEFAULTS.get(
        status_code,
        (
            "SERVER_ERROR" if status_code >= 500 else "UNKNOWN_ERROR",
            "Something went wrong" if status_code >= 500 else "Request failed",
        ),
    )
    details = payload if _include_details(status_code, payload) else None
    message = _extract_message(payload, default_message, status_code)
    return code, message, details, None


def _include_details(status_code: int, payload: Any) -> bool:
    if status_code >= 500:
        return False
    return isinstance(payload, (dict, list)) and payload not in (None, {})


def _extract_message(payload: Any, fallback: str, status_code: int) -> str:
    if status_code >= 500:
        default_server_message = STATUS_CODE_DEFAULTS.get(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            ("SERVER_ERROR", "Something went wrong"),
        )
        return default_server_message[1]
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
    if isinstance(payload, list) and payload and isinstance(payload[0], str):
        return payload[0]
    return fallback


__all__ = ["ApplicationError", "global_exception_handler"]
