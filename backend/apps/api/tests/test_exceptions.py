from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from apps.api.exceptions import ApplicationError, global_exception_handler

factory = APIRequestFactory()


class DummyView:
    pass


def _context(request):
    return {"request": request, "view": DummyView()}


def test_application_error_returns_structured_response():
    request = factory.get("/api/example/")
    exc = ApplicationError(
        "CONFLICT",
        "Cart already exists",
        status_code=status.HTTP_409_CONFLICT,
        details={"cartId": "abc123"},
    )
    response = global_exception_handler(exc, _context(request))
    payload = response.data["error"]
    assert response.status_code == status.HTTP_409_CONFLICT
    assert payload["code"] == "CONFLICT"
    assert payload["message"] == "Cart already exists"
    assert payload["details"] == {"cartId": "abc123"}


def test_validation_error_preserves_details():
    request = factory.post("/api/example/", data={})
    exc = ValidationError({"field": ["This field is required."]})
    response = global_exception_handler(exc, _context(request))
    payload = response.data["error"]
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["message"] == "Validation failed"
    assert payload["details"] == {"field": ["This field is required."]}


def test_unhandled_exception_returns_generic_message():
    request = factory.get("/api/example/")
    response = global_exception_handler(RuntimeError("boom"), _context(request))
    payload = response.data["error"]
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert payload["code"] == "SERVER_ERROR"
    assert payload["message"] == "Something went wrong"
    assert "details" not in payload

