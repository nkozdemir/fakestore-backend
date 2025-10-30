import types
from rest_framework.test import APIRequestFactory
from unittest.mock import patch
from apps.api.middleware import RequestValidationMiddleware
from apps.api.validation import (
    validate_request_context,
    _extract_request_data,
    _resolve_rating_user,
)
from apps.api.utils import error_response
from apps.catalog.views import (
    ProductRatingView,
    ProductListView,
    ProductDetailView,
    CategoryListView,
    CategoryDetailView,
)
from apps.carts.views import CartListView
from apps.users.views import (
    UserListView,
    UserDetailView,
    UserAddressListView,
    UserAddressDetailView,
)


factory = APIRequestFactory()


def test_validate_request_sets_cart_user_id():
    request = factory.post("/api/carts/", {}, format="json")
    request.user = types.SimpleNamespace(id=42, is_authenticated=True)
    response = validate_request_context(request, CartListView, {})
    assert response is None
    assert getattr(request, "validated_user_id", None) == 42


def test_validate_request_rating_get_ignores_invalid_header():
    request = factory.get("/api/products/1/rating/", HTTP_X_USER_ID="invalid")
    request.user = types.SimpleNamespace(id=11, is_authenticated=True)
    response = validate_request_context(request, ProductRatingView, {"product_id": 1})
    assert response is None
    assert getattr(request, "rating_user_id", None) == 11


def test_validate_request_rating_post_invalid_header_is_ignored_for_authenticated_user():
    request = factory.post(
        "/api/products/1/rating/", {"value": 4}, format="json", HTTP_X_USER_ID="invalid"
    )
    request.user = types.SimpleNamespace(id=15, is_authenticated=True)
    response = validate_request_context(request, ProductRatingView, {"product_id": 1})
    assert response is None
    assert getattr(request, "rating_user_id") == 15


def test_middleware_no_view_class_returns_none():
    middleware = RequestValidationMiddleware(lambda req: None)
    request = factory.get("/health/live")
    response = middleware.process_view(request, lambda req: req, [], {})
    assert response is None


def test_validate_request_rating_get_propagates_errors_from_helper():
    request = factory.get("/api/products/1/rating/")
    request.user = types.SimpleNamespace(id=23, is_authenticated=True)
    with patch(
        "apps.api.validation._resolve_rating_user",
        return_value=error_response("VALIDATION_ERROR", "bad", None),
    ) as resolve_mock:
        response = validate_request_context(
            request, ProductRatingView, {"product_id": 1}
        )
    assert response.status_code == 400
    resolve_mock.assert_called_once()


def test_validate_request_rating_authenticated_user_short_circuits():
    request = factory.post("/api/products/1/rating/", {"value": 3}, format="json")
    request.user = types.SimpleNamespace(id=9, is_authenticated=True)
    response = validate_request_context(request, ProductRatingView, {"product_id": 1})
    assert response is None
    assert getattr(request, "rating_user_id") == 9


@patch("apps.api.validation.User.objects")
def test_validate_request_user_post_duplicate(mock_user_manager):
    mock_user_manager.filter.return_value.exists.return_value = True
    request = factory.post("/api/users/", {"username": "dup"}, format="json")
    request.data = {"username": "dup"}
    request.user = types.SimpleNamespace(
        id=1, is_authenticated=True, is_staff=True, is_superuser=False
    )
    response = validate_request_context(request, UserListView, {})
    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


def test_validate_request_user_get_requires_auth():
    request = factory.get("/api/users/")
    response = validate_request_context(request, UserListView, {})
    assert response.status_code == 401


def test_validate_request_user_get_forbidden_for_non_admin():
    request = factory.get("/api/users/")
    request.user = types.SimpleNamespace(
        id=12, is_authenticated=True, is_staff=False, is_superuser=False
    )
    response = validate_request_context(request, UserListView, {})
    assert response.status_code == 403


def test_validate_request_user_get_allows_privileged():
    request = factory.get("/api/users/")
    request.user = types.SimpleNamespace(
        id=13, is_authenticated=True, is_staff=True, is_superuser=False
    )
    response = validate_request_context(request, UserListView, {})
    assert response is None
    assert getattr(request, "is_privileged_user") is True


@patch("apps.api.validation.User.objects")
def test_validate_request_user_put_duplicate_email(mock_user_manager):
    mock_user_manager.filter.return_value.exclude.return_value.exists.return_value = (
        True
    )
    request = factory.put("/api/users/2/", {"email": "dup@example.com"}, format="json")
    request.user = types.SimpleNamespace(
        id=2, is_authenticated=True, is_staff=False, is_superuser=False
    )
    response = validate_request_context(request, UserDetailView, {"user_id": 2})
    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


def test_validate_request_user_address_requires_auth():
    request = factory.post(
        "/api/users/4/addresses/", {"street": "Main"}, format="json"
    )
    response = validate_request_context(request, UserAddressListView, {"user_id": 4})
    assert response.status_code == 401


def test_validate_request_user_address_sets_validated_user():
    request = factory.get("/api/users/8/addresses/")
    request.user = types.SimpleNamespace(
        id=8, is_authenticated=True, is_superuser=False
    )
    response = validate_request_context(
        request, UserAddressListView, {"user_id": 8}
    )
    assert response is None
    assert getattr(request, "validated_user_id") == 8


def test_validate_request_user_address_detail_requires_auth():
    request = factory.get("/api/users/addresses/3/")
    response = validate_request_context(
        request, UserAddressDetailView, {"address_id": 3}
    )
    assert response.status_code == 401


def test_validate_request_user_address_detail_sets_validated_user():
    request = factory.get("/api/users/addresses/5/")
    request.user = types.SimpleNamespace(
        id=4, is_authenticated=True, is_superuser=True
    )
    response = validate_request_context(
        request, UserAddressDetailView, {"address_id": 5}
    )
    assert response is None
    assert getattr(request, "validated_user_id") == 4


def test_validate_request_category_post_requires_auth():
    request = factory.post("/api/categories/", {"name": "New"}, format="json")
    response = validate_request_context(request, CategoryListView, {})
    assert response.status_code == 401


def test_validate_request_category_post_forbidden_for_non_staff():
    request = factory.post("/api/categories/", {"name": "New"}, format="json")
    request.user = types.SimpleNamespace(
        id=2, is_authenticated=True, is_staff=False, is_superuser=False
    )
    response = validate_request_context(request, CategoryListView, {})
    assert response.status_code == 403


def test_validate_request_category_post_allows_staff():
    request = factory.post("/api/categories/", {"name": "New"}, format="json")
    request.user = types.SimpleNamespace(
        id=3, is_authenticated=True, is_staff=True, is_superuser=False
    )
    response = validate_request_context(request, CategoryListView, {})
    assert response is None
    assert getattr(request, "validated_user_id") == 3


def test_validate_request_category_detail_forbidden_for_non_staff():
    request = factory.patch("/api/categories/1/", {"name": "New"}, format="json")
    request.user = types.SimpleNamespace(
        id=4, is_authenticated=True, is_staff=False, is_superuser=False
    )
    response = validate_request_context(
        request, CategoryDetailView, {"category_id": 1}
    )
    assert response.status_code == 403


def test_validate_request_category_detail_allows_superuser():
    request = factory.delete("/api/categories/1/")
    request.user = types.SimpleNamespace(
        id=5, is_authenticated=True, is_staff=False, is_superuser=True
    )
    response = validate_request_context(
        request, CategoryDetailView, {"category_id": 1}
    )
    assert response is None
    assert getattr(request, "validated_user_id") == 5


def test_validate_request_user_address_forbidden_for_other_user():
    request = factory.get("/api/users/2/addresses/")
    request.user = types.SimpleNamespace(
        id=5, is_authenticated=True, is_superuser=False
    )
    response = validate_request_context(
        request, UserAddressListView, {"user_id": 2}
    )
    assert response.status_code == 403


def test_validate_request_user_address_allows_superuser():
    request = factory.get("/api/users/3/addresses/")
    request.user = types.SimpleNamespace(
        id=1, is_authenticated=True, is_superuser=True
    )
    response = validate_request_context(
        request, UserAddressListView, {"user_id": 3}
    )
    assert response is None
    assert getattr(request, "validated_user_id") == 1


def test_validate_request_product_post_requires_auth():
    request = factory.post("/api/products/", {"title": "X"}, format="json")
    response = validate_request_context(request, ProductListView, {})
    assert response.status_code == 401


def test_validate_request_product_post_forbidden_for_non_admin():
    request = factory.post("/api/products/", {"title": "X"}, format="json")
    request.user = types.SimpleNamespace(
        id=7, is_authenticated=True, is_staff=False, is_superuser=False
    )
    response = validate_request_context(request, ProductListView, {})
    assert response.status_code == 403


def test_validate_request_product_post_allows_admin():
    request = factory.post("/api/products/", {"title": "X"}, format="json")
    request.user = types.SimpleNamespace(
        id=8, is_authenticated=True, is_staff=True, is_superuser=False
    )
    response = validate_request_context(request, ProductListView, {})
    assert response is None
    assert getattr(request, "validated_user_id") == 8


def test_validate_request_product_detail_forbidden_for_non_admin():
    request = factory.patch("/api/products/1/", {"title": "New"}, format="json")
    request.user = types.SimpleNamespace(
        id=9, is_authenticated=True, is_staff=False, is_superuser=False
    )
    response = validate_request_context(
        request, ProductDetailView, {"product_id": 1}
    )
    assert response.status_code == 403


def test_validate_request_product_detail_allows_admin():
    request = factory.delete("/api/products/1/")
    request.user = types.SimpleNamespace(
        id=10, is_authenticated=True, is_staff=True, is_superuser=False
    )
    response = validate_request_context(
        request, ProductDetailView, {"product_id": 1}
    )
    assert response is None
    assert getattr(request, "validated_user_id") == 10


def test_validate_request_user_post_forbidden_when_authenticated_non_admin():
    request = factory.post("/api/users/", {"username": "new"}, format="json")
    request.user = types.SimpleNamespace(
        id=11, is_authenticated=True, is_staff=False, is_superuser=False
    )
    response = validate_request_context(request, UserListView, {})
    assert response.status_code == 403


@patch("apps.api.validation.User.objects")
def test_validate_request_user_post_unique(mock_user_manager):
    mock_user_manager.filter.return_value.exists.return_value = False
    request = factory.post("/api/users/", {"username": "unique"}, format="json")
    request.data = {"username": "unique"}
    request.user = types.SimpleNamespace(
        id=1, is_authenticated=True, is_staff=True, is_superuser=False
    )
    response = validate_request_context(request, UserListView, {})
    assert response is None


def test_extract_request_data_handles_invalid_json():
    request = types.SimpleNamespace(
        content_type="application/json", body=b"\xff", data=None, POST={}
    )
    data = _extract_request_data(request)
    assert data == {}


def test_extract_request_data_form_payload():
    request = factory.post("/api/users/", {"username": "form-user"})
    data = _extract_request_data(request)
    assert data.get("username") == "form-user"


def test_extract_request_data_defaults_to_empty():
    request = types.SimpleNamespace(content_type="", data=None, POST={})
    data = _extract_request_data(request)
    assert data == {}


def test_resolve_rating_user_without_identifier():
    request = types.SimpleNamespace(user=None, headers={}, GET={})
    response = _resolve_rating_user(request, require=False)
    assert response is None
    assert getattr(request, "rating_user_id") is None


def test_extract_request_data_without_post_attribute():
    request = types.SimpleNamespace(content_type="", data=None)
    data = _extract_request_data(request)
    assert data == {}
