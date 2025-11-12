from __future__ import annotations

from typing import Iterable, Optional

from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext_lazy as _

_DEFAULT_LANGUAGE = (
    (getattr(settings, "LANGUAGE_CODE", "en") or "en").split("-")[0].lower()
)
_SUPPORTED_LANGUAGES = {
    (code or "en").split("-")[0].lower()
    for code, _ in getattr(settings, "LANGUAGES", [("en", "English")])
} or {_DEFAULT_LANGUAGE}


def normalize_language_code(language_code: Optional[str]) -> str:
    """
    Normalize a language code to lowercase without region (~ RFC 5646 style).
    Unknown languages fall back to the project default.
    """

    if not language_code:
        language_code = translation.get_language()
    if not language_code:
        return _DEFAULT_LANGUAGE
    normalized = language_code.split("-")[0].lower()
    return normalized if normalized in _SUPPORTED_LANGUAGES else _DEFAULT_LANGUAGE


def resolve_language(request=None, fallback: Optional[str] = None) -> str:
    """
    Resolve the best language for the current request context.
    """

    language_code = None
    if request is not None:
        query = None
        try:
            query = getattr(request, "GET", None)
            if query:
                query_code = query.get("lang") or query.get("language")
                if query_code:
                    language_code = query_code
        except Exception:
            language_code = None
        if not language_code:
            language_code = getattr(request, "LANGUAGE_CODE", None)
        if not language_code:
            try:
                language_code = translation.get_language_from_request(request)
            except Exception:
                language_code = None
    language_code = language_code or translation.get_language() or fallback
    return normalize_language_code(language_code)


def is_supported_language(language_code: Optional[str]) -> bool:
    if not language_code:
        return False
    normalized = language_code.split("-")[0].lower()
    return normalized in _SUPPORTED_LANGUAGES


def is_default_language(language_code: Optional[str]) -> bool:
    return normalize_language_code(language_code) == _DEFAULT_LANGUAGE


def iter_supported_languages() -> Iterable[str]:
    return sorted(_SUPPORTED_LANGUAGES)


def get_default_language() -> str:
    return _DEFAULT_LANGUAGE


# Central catalogue of user-visible error messages so makemessages can extract them
# even when they are only used dynamically via error_response.
TRANSLATABLE_ERROR_MESSAGES = (
    _("Product not found"),
    _("Category not found"),
    _("Cart not found"),
    _("User not found"),
    _("Address not found"),
    _("Authentication required"),
    _("Invalid input"),
    _("Invalid user identifier"),
    _("Invalid value"),
    _("Email already exists"),
    _("Username already exists"),
    _("Target user already has a cart"),
    _("You do not have permission to create users"),
    _("You do not have permission to list users"),
    _("You do not have permission to view or modify this user"),
    _("You do not have permission to manage this user's addresses"),
    _("You do not have permission to create carts for other users"),
    _("You do not have permission to list carts"),
    _("You do not have permission to manage categories"),
    _("You do not have permission to manage products"),
    _("You do not have permission to view this user's carts"),
    _("Staff and admin accounts cannot rate products for themselves"),
    _("ratingId is required"),
    _("ratingId must be an integer"),
    _("userId must be an integer"),
    _("value must be between 0 and 5"),
    _("Something went wrong"),
    _("bad"),
    _("missing"),
    _("oops"),
)


__all__ = [
    "normalize_language_code",
    "resolve_language",
    "is_supported_language",
    "is_default_language",
    "iter_supported_languages",
    "get_default_language",
]
