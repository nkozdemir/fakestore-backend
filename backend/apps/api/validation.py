import json
from typing import Any, Dict, Optional
from django.http import HttpRequest
from apps.api.utils import error_response
from apps.users.models import User
from apps.common import get_logger

logger = get_logger(__name__).bind(component='api', layer='validation')


def _is_authenticated_user(request: HttpRequest) -> bool:
    user = getattr(request, 'user', None)
    return bool(user and getattr(user, 'is_authenticated', False) and getattr(user, 'id', None))


def _set_validated_user(request: HttpRequest, user_id: Optional[int]) -> None:
    request.validated_user_id = user_id


def _extract_request_data(request: HttpRequest) -> Dict[str, Any]:
    data = getattr(request, 'data', None)
    if data not in (None, {}):
        return data
    if request.content_type == 'application/json':
        try:
            body = request.body.decode('utf-8') if hasattr(request, 'body') else None
            return json.loads(body) if body else {}
        except (ValueError, AttributeError, UnicodeDecodeError):
            return {}
    if hasattr(request, 'POST'):
        post = request.POST
        if hasattr(post, 'dict'):
            return post.dict()
        return dict(post)
    return {}


def _resolve_rating_user(request: HttpRequest, require: bool) -> Any:  # pragma: no cover - exercised via middleware dispatch
    if _is_authenticated_user(request):
        user_id = int(request.user.id)
        request.rating_user_id = user_id
        logger.debug('Resolved rating user from authentication', user_id=user_id)
        return None
    uid_candidate = request.headers.get('X-User-Id') or request.GET.get('userId')
    if uid_candidate is None:
        if require:
            logger.warning('Rating user required but missing')
            return error_response('VALIDATION_ERROR', 'Authentication required', None)
        request.rating_user_id = None
        logger.debug('No rating user provided; proceeding without user')
        return None
    try:
        user_id = int(uid_candidate)
    except (TypeError, ValueError):
        if require:
            logger.warning('Invalid rating user identifier', value=uid_candidate)
            return error_response('VALIDATION_ERROR', 'Invalid user identifier', {'userId': uid_candidate})
        request.rating_user_id = None
        logger.debug('Invalid rating user identifier ignored', value=uid_candidate)
        return None
    request.rating_user_id = user_id
    logger.debug('Resolved rating user from header/context', user_id=user_id)
    return None


def _resolve_category_ids(request: HttpRequest) -> Any:
    raw = request.GET.get('categoryIds')
    if raw is None:
        request.category_ids = []
        logger.debug('No categoryIds provided')
        return None
    try:
        ids = [int(item) for item in raw.split(',') if item.strip()]
    except ValueError:
        logger.warning('Invalid categoryIds parameter', value=raw)
        return error_response('VALIDATION_ERROR', 'Invalid categoryIds parameter', {'categoryIds': raw})
    request.category_ids = ids
    logger.debug('Resolved categoryIds parameter', category_ids=ids)
    return None


def _validate_user_uniqueness(request: HttpRequest, user_id: Optional[int] = None) -> Any:
    data = _extract_request_data(request) or {}
    username = data.get('username')
    email = data.get('email')

    def _exists(field: str, value: str) -> bool:
        qs = User.objects.filter(**{field: value})
        if user_id:
            qs = qs.exclude(id=user_id)
        return qs.exists()

    if username and _exists('username', username):
        logger.info('Username uniqueness validation failed', username=username, user_id=user_id)
        return error_response('VALIDATION_ERROR', 'Username already exists', {'field': 'username', 'value': username})
    if email and _exists('email', email):
        logger.info('Email uniqueness validation failed', email=email, user_id=user_id)
        return error_response('VALIDATION_ERROR', 'Email already exists', {'field': 'email', 'value': email})
    return None


def validate_request_context(request: HttpRequest, view_class, view_kwargs) -> Any:
    """
    Performs request level validation for specific API views.
    Returns a DRF Response when validation fails; otherwise None and
    attaches validated data to the request instance.
    """
    view_name = getattr(view_class, '__name__', '')

    logger.debug('Running request context validation', view=view_name, method=getattr(request, 'method', None))

    if view_name == 'CartListView':
        if request.method in ('POST',):
            if not _is_authenticated_user(request):
                logger.warning('CartListView POST requires authentication')
                return error_response('UNAUTHORIZED', 'Authentication required')
            _set_validated_user(request, int(request.user.id))
            logger.debug('Validated cart list user', user_id=request.user.id)
    elif view_name == 'CartDetailView':
        if request.method in ('PUT', 'PATCH', 'DELETE'):
            if not _is_authenticated_user(request):
                logger.warning('CartDetailView requires authentication', method=request.method)
                return error_response('UNAUTHORIZED', 'Authentication required')
            _set_validated_user(request, int(request.user.id))
            logger.debug('Validated cart detail user', user_id=request.user.id)
    elif view_name == 'ProductRatingView':
        if request.method in ('POST', 'DELETE'):
            resp = _resolve_rating_user(request, require=True)
            if resp:
                logger.warning('Product rating validation rejected request', method=request.method)
                return resp
        else:
            resp = _resolve_rating_user(request, require=False)
            if resp:
                logger.warning('Product rating validation rejected request', method=request.method)
                return resp
    elif view_name == 'ProductByCategoriesView':
        resp = _resolve_category_ids(request)
        if resp:
            logger.warning('ProductByCategoriesView validation failed')
            return resp
    elif view_name == 'UserListView':
        if request.method in ('POST', 'PUT', 'PATCH'):
            result = _validate_user_uniqueness(request)
            if result:
                logger.info('UserListView uniqueness check failed')
                return result
    elif view_name == 'UserDetailView':
        if request.method in ('PUT', 'PATCH'):
            user_id = view_kwargs.get('user_id')
            result = _validate_user_uniqueness(request, user_id=user_id)
            if result:
                logger.info('UserDetailView uniqueness check failed', user_id=user_id)
                return result
    elif view_name in ('UserAddressListView', 'UserAddressDetailView'):
        if not _is_authenticated_user(request):
            logger.warning('User address view requires authentication', view=view_name)
            return error_response('UNAUTHORIZED', 'Authentication required')
        _set_validated_user(request, int(request.user.id))
        logger.debug('Validated user for address request', user_id=request.user.id, view=view_name)

    return None
