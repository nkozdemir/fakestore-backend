import json
from typing import Any, Dict, Optional

from django.http import HttpRequest
from django.utils.translation import gettext as _
from rest_framework.exceptions import AuthenticationFailed as DRFAuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from apps.api.utils import error_response
from apps.users.models import User
from apps.common import get_logger

logger = get_logger(__name__).bind(component="api", layer="validation")

_jwt_authenticator = JWTAuthentication()


def _is_authenticated_user(request: HttpRequest) -> bool:
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False) and getattr(user, "id", None):
        return True

    # DRF attaches the authenticated user later in the request lifecycle. Since this
    # middleware runs earlier, attempt JWT authentication manually to support bearer tokens.
    meta = getattr(request, "META", {}) or {}
    auth_header = meta.get("HTTP_AUTHORIZATION") if hasattr(meta, "get") else None
    if not auth_header:
        return False

    try:
        authenticated = _jwt_authenticator.authenticate(request)
    except (InvalidToken, DRFAuthenticationFailed) as exc:
        logger.warning("JWT authentication failed", detail=str(exc))
        return False

    if not authenticated:
        return False

    user, token = authenticated
    if not getattr(user, "is_authenticated", False) or not getattr(user, "id", None):
        return False

    # Mirror DRF's behaviour so downstream consumers see the authenticated user.
    request.user = user
    request.auth = token
    request.is_privileged_user = _is_privileged_user(user)
    logger.debug("Authenticated user from bearer token", user_id=user.id)
    return True


def _set_validated_user(request: HttpRequest, user_id: Optional[int]) -> None:
    request.validated_user_id = user_id
    if hasattr(request, "user"):
        request.is_privileged_user = _is_privileged_user(getattr(request, "user", None))


def _is_privileged_user(user: Any) -> bool:
    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


def _extract_request_data(request: HttpRequest) -> Dict[str, Any]:
    data = getattr(request, "data", None)
    if data not in (None, {}):
        return data
    if request.content_type == "application/json":
        try:
            body = request.body.decode("utf-8") if hasattr(request, "body") else None
            return json.loads(body) if body else {}
        except (ValueError, AttributeError, UnicodeDecodeError):
            return {}
    if hasattr(request, "POST"):
        post = request.POST
        if hasattr(post, "dict"):
            return post.dict()
        return dict(post)
    return {}


def _resolve_rating_user(
    request: HttpRequest, require: bool
) -> Any:  # pragma: no cover - exercised via middleware dispatch
    if _is_authenticated_user(request):
        user_id = int(request.user.id)
        request.rating_user_id = user_id
        logger.debug("Resolved rating user from authentication", user_id=user_id)
        return None
    uid_candidate = request.headers.get("X-User-Id") or request.GET.get("userId")
    if uid_candidate is None:
        if require:
            logger.warning("Rating user required but missing")
            return error_response("VALIDATION_ERROR", "Authentication required", None)
        request.rating_user_id = None
        logger.debug("No rating user provided; proceeding without user")
        return None
    try:
        user_id = int(uid_candidate)
    except (TypeError, ValueError):
        if require:
            logger.warning("Invalid rating user identifier", value=uid_candidate)
            return error_response(
                "VALIDATION_ERROR", "Invalid user identifier", {"userId": uid_candidate}
            )
        request.rating_user_id = None
        logger.debug("Invalid rating user identifier ignored", value=uid_candidate)
        return None
    request.rating_user_id = user_id
    logger.debug("Resolved rating user from header/context", user_id=user_id)
    return None


def _rating_override_forbidden_message(method: str) -> str:
    if method == "GET":
        return _("You do not have permission to view ratings for other users")
    if method == "POST":
        return _("You do not have permission to rate on behalf of other users")
    return _("You do not have permission to manage ratings for other users")


def _apply_rating_user_override(
    request: HttpRequest,
    *,
    method: str,
    is_privileged: bool,
    resolved_user_id: Optional[int],
    actor_id: Optional[int],
) -> Any:
    raw_user_id = request.GET.get("userId") or request.GET.get("user_id")
    if raw_user_id is None:
        request.rating_target_user_id = resolved_user_id
        return None
    try:
        desired_user_id = int(raw_user_id)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid userId query parameter provided",
            view="ProductRatingView",
            method=method,
            actor_id=actor_id,
            raw_value=raw_user_id,
        )
        return error_response(
            "VALIDATION_ERROR",
            "userId must be an integer",
            {"userId": raw_user_id},
        )
    if is_privileged:
        request.rating_target_user_id = desired_user_id
        request.rating_user_override_applied = True
        request.rating_requested_user_id = desired_user_id
        return None
    if resolved_user_id is None or desired_user_id != resolved_user_id:
        logger.warning(
            "Rating override forbidden",
            view="ProductRatingView",
            method=method,
            actor_id=actor_id,
            requested_user_id=desired_user_id,
            resolved_user_id=resolved_user_id,
        )
        return error_response(
            "FORBIDDEN",
            _rating_override_forbidden_message(method),
            {"userId": str(desired_user_id)},
        )
    request.rating_target_user_id = resolved_user_id
    return None


def _parse_rating_value(request: HttpRequest, *, product_id: Optional[int]) -> Any:
    data = _extract_request_data(request) or {}
    value = data.get("value")
    try:
        rating_value = int(value)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid rating payload",
            view="ProductRatingView",
            product_id=product_id,
            value=value,
        )
        return error_response(
            "VALIDATION_ERROR",
            "value must be between 0 and 5",
            {"value": value},
        )
    request.rating_value = rating_value
    return None


def _parse_rating_identifier(request: HttpRequest, *, product_id: Optional[int], actor_id: Optional[int]) -> Any:
    raw_rating_id = request.GET.get("ratingId") or request.GET.get("rating_id")
    if raw_rating_id is None:
        logger.warning(
            "Rating delete missing identifier",
            view="ProductRatingView",
            product_id=product_id,
            actor_id=actor_id,
        )
        return error_response(
            "VALIDATION_ERROR", "ratingId is required", {"ratingId": None}
        )
    try:
        rating_id = int(raw_rating_id)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid ratingId parameter",
            view="ProductRatingView",
            product_id=product_id,
            actor_id=actor_id,
            raw_value=raw_rating_id,
        )
        return error_response(
            "VALIDATION_ERROR",
            "ratingId must be an integer",
            {"ratingId": raw_rating_id},
        )
    request.rating_id = rating_id
    return None


def _validate_user_uniqueness(
    request: HttpRequest, user_id: Optional[int] = None
) -> Any:
    data = _extract_request_data(request) or {}
    username = data.get("username")
    email = data.get("email")

    def _exists(field: str, value: str) -> bool:
        qs = User.objects.filter(**{field: value})
        if user_id:
            qs = qs.exclude(id=user_id)
        return qs.exists()

    if username and _exists("username", username):
        logger.info(
            "Username uniqueness validation failed", username=username, user_id=user_id
        )
        return error_response(
            "VALIDATION_ERROR",
            "Username already exists",
            {"field": "username", "value": username},
        )
    if email and _exists("email", email):
        logger.info("Email uniqueness validation failed", email=email, user_id=user_id)
        return error_response(
            "VALIDATION_ERROR",
            "Email already exists",
            {"field": "email", "value": email},
        )
    return None


def validate_request_context(request: HttpRequest, view_class, view_kwargs) -> Any:
    """
    Performs request level validation for specific API views.
    Returns a DRF Response when validation fails; otherwise None and
    attaches validated data to the request instance.
    """
    view_name = getattr(view_class, "__name__", "")

    logger.debug(
        "Running request context validation",
        view=view_name,
        method=getattr(request, "method", None),
    )

    if view_name == "CartListView":
        if request.method in ("GET",):
            if not _is_authenticated_user(request):
                logger.warning("CartListView GET requires authentication")
                return error_response("UNAUTHORIZED", "Authentication required")
            actor_id = int(request.user.id)
            _set_validated_user(request, actor_id)
            is_privileged = _is_privileged_user(request.user)
            request.cart_is_privileged = is_privileged
            request.cart_list_mode = "all"
            request.cart_list_target_user_id = None
            raw_user_id = request.GET.get("userId") or request.GET.get("user_id")
            if raw_user_id is not None:
                try:
                    target_user_id = int(raw_user_id)
                except (TypeError, ValueError):
                    logger.warning(
                        "Invalid userId query parameter",
                        view=view_name,
                        value=raw_user_id,
                    )
                    return error_response(
                        "VALIDATION_ERROR",
                        "userId must be an integer",
                        {"userId": raw_user_id},
                    )
                request.cart_list_target_user_id = target_user_id
                if is_privileged:
                    request.cart_list_mode = "filtered"
                elif actor_id == target_user_id:
                    request.cart_list_mode = "self"
                else:
                    logger.warning(
                        "Cart list forbidden for non-privileged override",
                        actor_id=actor_id,
                        target_user_id=target_user_id,
                    )
                    return error_response(
                        "FORBIDDEN",
                        "You do not have permission to view this user's carts",
                        {"userId": raw_user_id},
                    )
            else:
                if not is_privileged:
                    logger.warning(
                        "Cart list forbidden for non-privileged user",
                        actor_id=actor_id,
                    )
                    return error_response(
                        "FORBIDDEN",
                        "You do not have permission to list carts",
                    )
            logger.debug(
                "Validated cart list context",
                actor_id=actor_id,
                privileged=is_privileged,
                mode=request.cart_list_mode,
                target_user_id=request.cart_list_target_user_id,
            )
        if request.method in ("POST",):
            if not _is_authenticated_user(request):
                logger.warning("CartListView POST requires authentication")
                return error_response("UNAUTHORIZED", "Authentication required")
            actor_id = int(request.user.id)
            _set_validated_user(request, actor_id)
            is_privileged = _is_privileged_user(request.user)
            raw_user_id = request.GET.get("userId") or request.GET.get("user_id")
            target_user_id = actor_id
            if raw_user_id is not None:
                try:
                    desired_user_id = int(raw_user_id)
                except (TypeError, ValueError):
                    logger.warning(
                        "Invalid userId query parameter provided for cart creation",
                        raw_value=raw_user_id,
                    )
                    return error_response(
                        "VALIDATION_ERROR",
                        "userId must be an integer",
                        {"userId": raw_user_id},
                    )
                if is_privileged:
                    target_user_id = desired_user_id
                elif desired_user_id != actor_id:
                    logger.warning(
                        "Cart creation forbidden for non-privileged override",
                        actor_id=actor_id,
                        desired_user_id=desired_user_id,
                    )
                    return error_response(
                        "FORBIDDEN",
                        "You do not have permission to create carts for other users",
                        {"userId": str(desired_user_id)},
                    )
            request.cart_target_user_id = target_user_id
            request.cart_is_privileged = is_privileged
            logger.debug(
                "Validated cart creation context",
                actor_id=actor_id,
                target_user_id=target_user_id,
                privileged=is_privileged,
            )
    elif view_name == "CartDetailView":
        if request.method in ("GET", "PUT", "PATCH", "DELETE"):
            if not _is_authenticated_user(request):
                logger.warning(
                    "CartDetailView requires authentication", method=request.method
                )
                return error_response("UNAUTHORIZED", "Authentication required")
            _set_validated_user(request, int(request.user.id))
            logger.debug(
                "Validated cart detail user",
                user_id=request.user.id,
                method=request.method,
            )
    elif view_name == "ProductRatingView":
        method = getattr(request, "method", "")
        product_id = view_kwargs.get("product_id")
        if not _is_authenticated_user(request):
            logger.warning(
                "ProductRatingView requires authentication", method=method
            )
            return error_response("UNAUTHORIZED", "Authentication required")
        resp = _resolve_rating_user(request, require=method in ("POST", "DELETE"))
        if resp:
            logger.warning(
                "Product rating validation rejected request", method=method
            )
            return resp
        actor = getattr(request, "user", None)
        actor_id = getattr(actor, "id", None)
        request.rating_actor_id = actor_id
        is_staff = bool(
            getattr(actor, "is_staff", False) or getattr(actor, "is_superuser", False)
        )
        request.rating_is_staff = is_staff
        is_privileged = bool(getattr(request, "is_privileged_user", False) or is_staff)
        request.rating_is_privileged = is_privileged
        resolved_user_id = getattr(request, "rating_user_id", None)
        request.rating_target_user_id = resolved_user_id
        if method in ("POST", "DELETE") and is_staff and (
            resolved_user_id is None or resolved_user_id == actor_id
        ):
            log_message = (
                "Staff/admin attempted to rate own account"
                if method == "POST"
                else "Staff/admin attempted to delete own rating"
            )
            logger.warning(
                log_message,
                view="ProductRatingView",
                product_id=product_id,
                actor_id=actor_id,
            )
            return error_response(
                "FORBIDDEN",
                "Staff and admin accounts cannot rate products for themselves",
            )
        override_response = _apply_rating_user_override(
            request,
            method=method,
            is_privileged=is_privileged,
            resolved_user_id=resolved_user_id,
            actor_id=actor_id,
        )
        if override_response:
            return override_response
        target_user_id = getattr(request, "rating_target_user_id", resolved_user_id)
        if method in ("POST", "DELETE") and target_user_id is None:
            logger.warning(
                "Rating action missing user identifier",
                view="ProductRatingView",
                method=method,
                product_id=product_id,
                actor_id=actor_id,
            )
            return error_response(
                "VALIDATION_ERROR", "Authentication required", {"userId": None}
            )
        if method == "POST":
            resp = _parse_rating_value(request, product_id=product_id)
            if resp:
                return resp
        if method == "DELETE":
            resp = _parse_rating_identifier(
                request, product_id=product_id, actor_id=actor_id
            )
            if resp:
                return resp
    elif view_name == "UserListView":
        if request.method in ("GET",):
            if not _is_authenticated_user(request):
                logger.warning("UserListView GET requires authentication")
                return error_response("UNAUTHORIZED", "Authentication required")
            if not _is_privileged_user(request.user):
                logger.warning(
                    "UserListView GET forbidden",
                    user_id=getattr(request.user, "id", None),
                )
                return error_response(
                    "FORBIDDEN",
                    "You do not have permission to list users",
                )
            request.is_privileged_user = True
        if request.method in ("POST",):
            if not _is_authenticated_user(request):
                logger.warning("UserListView POST requires authentication")
                return error_response("UNAUTHORIZED", "Authentication required")
            if not _is_privileged_user(request.user):
                logger.warning(
                    "UserListView POST forbidden",
                    user_id=getattr(request.user, "id", None),
                )
                return error_response(
                    "FORBIDDEN", "You do not have permission to create users"
                )
        if request.method in ("POST", "PUT", "PATCH"):
            result = _validate_user_uniqueness(request)
            if result:
                logger.info("UserListView uniqueness check failed")
                return result
    elif view_name == "CategoryListView":
        if request.method in ("POST",):
            if not _is_authenticated_user(request):
                logger.warning("CategoryListView POST requires authentication")
                return error_response("UNAUTHORIZED", "Authentication required")
            _set_validated_user(request, int(request.user.id))
            if not _is_privileged_user(request.user):
                logger.warning(
                    "CategoryListView POST forbidden",
                    user_id=request.user.id,
                )
                return error_response(
                    "FORBIDDEN",
                    "You do not have permission to manage categories",
                )
    elif view_name == "ProductListView":
        if request.method in ("POST",):
            if not _is_authenticated_user(request):
                logger.warning("ProductListView POST requires authentication")
                return error_response("UNAUTHORIZED", "Authentication required")
            _set_validated_user(request, int(request.user.id))
            if not _is_privileged_user(request.user):
                logger.warning(
                    "ProductListView POST forbidden",
                    user_id=request.user.id,
                )
                return error_response(
                    "FORBIDDEN",
                    "You do not have permission to manage products",
                )
    elif view_name == "UserDetailView":
        target_raw = view_kwargs.get("user_id")
        try:
            target_user_id = int(target_raw)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid user_id for user detail request",
                value=target_raw,
                method=request.method,
            )
            return error_response(
                "VALIDATION_ERROR",
                "Invalid user identifier",
                {"userId": str(target_raw)},
            )
        if not _is_authenticated_user(request):
            logger.warning(
                "UserDetailView requires authentication",
                method=request.method,
                target_user_id=target_user_id,
            )
            return error_response("UNAUTHORIZED", "Authentication required")
        actor_id = int(request.user.id)
        _set_validated_user(request, actor_id)
        is_privileged = _is_privileged_user(request.user)
        request.user_detail_target_id = target_user_id
        request.user_detail_is_privileged = is_privileged
        if request.method in ("GET", "PUT", "PATCH", "DELETE") and not is_privileged and actor_id != target_user_id:
            logger.warning(
                "User detail access forbidden",
                method=request.method,
                actor_id=actor_id,
                target_user_id=target_user_id,
            )
            return error_response(
                "FORBIDDEN",
                "You do not have permission to view or modify this user",
            )
        if request.method in ("PUT", "PATCH"):
            result = _validate_user_uniqueness(request, user_id=target_user_id)
            if result:
                logger.info(
                    "UserDetailView uniqueness check failed",
                    user_id=target_user_id,
                )
                return result
    elif view_name == "CategoryDetailView":
        if request.method in ("PUT", "PATCH", "DELETE"):
            if not _is_authenticated_user(request):
                logger.warning(
                    "CategoryDetailView modification requires authentication",
                    method=request.method,
                )
                return error_response("UNAUTHORIZED", "Authentication required")
            _set_validated_user(request, int(request.user.id))
            if not _is_privileged_user(request.user):
                logger.warning(
                    "CategoryDetailView modification forbidden",
                    user_id=request.user.id,
                    method=request.method,
                )
                return error_response(
                    "FORBIDDEN",
                    "You do not have permission to manage categories",
                )
    elif view_name == "ProductDetailView":
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            # POST not used here but keep symmetrical
            if not _is_authenticated_user(request):
                logger.warning(
                    "ProductDetailView modification requires authentication",
                    method=request.method,
                )
                return error_response("UNAUTHORIZED", "Authentication required")
            _set_validated_user(request, int(request.user.id))
            if not _is_privileged_user(request.user):
                logger.warning(
                    "ProductDetailView modification forbidden",
                    user_id=request.user.id,
                    method=request.method,
                )
                return error_response(
                    "FORBIDDEN",
                    "You do not have permission to manage products",
                )
    elif view_name == "CartByUserView":
        if request.method in ("GET",):
            if not _is_authenticated_user(request):
                logger.warning("CartByUserView GET requires authentication")
                return error_response("UNAUTHORIZED", "Authentication required")
            actor_id = int(request.user.id)
            _set_validated_user(request, actor_id)
            target_user_id = view_kwargs.get("user_id")
            try:
                target_user_id = int(target_user_id)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid user_id in cart-by-user request",
                    value=target_user_id,
                )
                return error_response(
                    "VALIDATION_ERROR",
                    "Invalid user identifier",
                    {"userId": str(target_user_id)},
                )
            if not _is_privileged_user(request.user) and actor_id != target_user_id:
                logger.warning(
                    "CartByUserView GET forbidden",
                    actor_id=actor_id,
                    target_user_id=target_user_id,
                )
                return error_response(
                    "FORBIDDEN",
                    "You do not have permission to view this user's carts",
                )
    elif view_name in ("UserAddressListView", "UserAddressDetailView"):
        if not _is_authenticated_user(request):
            logger.warning("User address view requires authentication", view=view_name)
            return error_response("UNAUTHORIZED", "Authentication required")
        actor_id = int(request.user.id)
        _set_validated_user(request, actor_id)
        target_user_id = view_kwargs.get("user_id")
        if target_user_id is not None:
            try:
                target_user_id = int(target_user_id)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid user_id in address request",
                    view=view_name,
                    value=target_user_id,
                )
                return error_response(
                    "VALIDATION_ERROR",
                    "Invalid user identifier",
                    {"userId": str(target_user_id)},
                )
            is_superuser = bool(getattr(request.user, "is_superuser", False))
            if actor_id != target_user_id and not is_superuser:
                logger.warning(
                    "Address request forbidden for user",
                    actor_id=actor_id,
                    target_user_id=target_user_id,
                    view=view_name,
                )
                return error_response(
                    "FORBIDDEN",
                    "You do not have permission to manage this user's addresses",
                )
        logger.debug(
            "Validated user for address request",
            user_id=actor_id,
            target_user_id=target_user_id,
            view=view_name,
        )

    return None
