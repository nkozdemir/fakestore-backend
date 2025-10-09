import types
from rest_framework.test import APIRequestFactory
from unittest.mock import patch
from apps.api.middleware import RequestValidationMiddleware
from apps.api.validation import validate_request_context, _extract_request_data, _resolve_rating_user
from apps.api.utils import error_response
from apps.catalog.views import ProductByCategoriesView, ProductRatingView
from apps.carts.views import CartListView
from apps.users.views import UserListView, UserDetailView, UserAddressListView


factory = APIRequestFactory()


def test_middleware_returns_error_for_invalid_category_ids():
    request = factory.get('/api/products/by-categories/', {'categoryIds': 'bad'})
    middleware = RequestValidationMiddleware(lambda req: None)
    view_func = ProductByCategoriesView.as_view()
    response = middleware.process_view(request, view_func, [], {})
    assert response.status_code == 400
    assert response.data['error']['code'] == 'VALIDATION_ERROR'


def test_validate_request_sets_cart_user_id():
    request = factory.post('/api/carts/', {}, format='json')
    request.user = types.SimpleNamespace(id=42, is_authenticated=True)
    response = validate_request_context(request, CartListView, {})
    assert response is None
    assert getattr(request, 'validated_user_id', None) == 42


def test_validate_request_rating_get_ignores_invalid_header():
    request = factory.get('/api/products/1/rating/', HTTP_X_USER_ID='invalid')
    response = validate_request_context(request, ProductRatingView, {'product_id': 1})
    assert response is None
    assert getattr(request, 'rating_user_id', 'missing') is None


def test_validate_request_rating_post_invalid_header_errors():
    request = factory.post('/api/products/1/rating/', {'value': 4}, format='json', HTTP_X_USER_ID='invalid')
    response = validate_request_context(request, ProductRatingView, {'product_id': 1})
    assert response.status_code == 400
    assert response.data['error']['code'] == 'VALIDATION_ERROR'


def test_middleware_no_view_class_returns_none():
    middleware = RequestValidationMiddleware(lambda req: None)
    request = factory.get('/health/live')
    response = middleware.process_view(request, lambda req: req, [], {})
    assert response is None


def test_validate_request_rating_get_propagates_errors_from_helper():
    request = factory.get('/api/products/1/rating/')
    with patch('apps.api.validation._resolve_rating_user', return_value=error_response('VALIDATION_ERROR', 'bad', None)) as resolve_mock:
        response = validate_request_context(request, ProductRatingView, {'product_id': 1})
    assert response.status_code == 400
    resolve_mock.assert_called_once()


def test_validate_request_rating_authenticated_user_short_circuits():
    request = factory.post('/api/products/1/rating/', {'value': 3}, format='json')
    request.user = types.SimpleNamespace(id=9, is_authenticated=True)
    response = validate_request_context(request, ProductRatingView, {'product_id': 1})
    assert response is None
    assert getattr(request, 'rating_user_id') == 9


@patch('apps.api.validation.User.objects')
def test_validate_request_user_post_duplicate(mock_user_manager):
    mock_user_manager.filter.return_value.exists.return_value = True
    request = factory.post('/api/users/', {'username': 'dup'}, format='json')
    request.data = {'username': 'dup'}
    response = validate_request_context(request, UserListView, {})
    assert response.status_code == 400
    assert response.data['error']['code'] == 'VALIDATION_ERROR'


@patch('apps.api.validation.User.objects')
def test_validate_request_user_put_duplicate_email(mock_user_manager):
    mock_user_manager.filter.return_value.exclude.return_value.exists.return_value = True
    request = factory.put('/api/users/2/', {'email': 'dup@example.com'}, format='json')
    response = validate_request_context(request, UserDetailView, {'user_id': 2})
    assert response.status_code == 400
    assert response.data['error']['code'] == 'VALIDATION_ERROR'


def test_validate_request_user_address_requires_auth():
    request = factory.post('/api/users/me/addresses/', {'street': 'Main'}, format='json')
    response = validate_request_context(request, UserAddressListView, {})
    assert response.status_code == 401


def test_validate_request_user_address_sets_validated_user():
    request = factory.get('/api/users/me/addresses/')
    request.user = types.SimpleNamespace(id=8, is_authenticated=True)
    response = validate_request_context(request, UserAddressListView, {})
    assert response is None
    assert getattr(request, 'validated_user_id') == 8


@patch('apps.api.validation.User.objects')
def test_validate_request_user_post_unique(mock_user_manager):
    mock_user_manager.filter.return_value.exists.return_value = False
    request = factory.post('/api/users/', {'username': 'unique'}, format='json')
    request.data = {'username': 'unique'}
    response = validate_request_context(request, UserListView, {})
    assert response is None


def test_extract_request_data_handles_invalid_json():
    request = types.SimpleNamespace(content_type='application/json', body=b'\xff', data=None, POST={})
    data = _extract_request_data(request)
    assert data == {}


def test_extract_request_data_form_payload():
    request = factory.post('/api/users/', {'username': 'form-user'})
    data = _extract_request_data(request)
    assert data.get('username') == 'form-user'


def test_extract_request_data_defaults_to_empty():
    request = types.SimpleNamespace(content_type='', data=None, POST={})
    data = _extract_request_data(request)
    assert data == {}


def test_resolve_rating_user_without_identifier():
    request = types.SimpleNamespace(user=None, headers={}, GET={})
    response = _resolve_rating_user(request, require=False)
    assert response is None
    assert getattr(request, 'rating_user_id') is None


def test_extract_request_data_without_post_attribute():
    request = types.SimpleNamespace(content_type='', data=None)
    data = _extract_request_data(request)
    assert data == {}
