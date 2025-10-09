from django.utils.deprecation import MiddlewareMixin
from apps.api.validation import validate_request_context


class RequestValidationMiddleware(MiddlewareMixin):
    """
    Centralised request validation middleware that ensures authentication- and
    query-related checks are executed before hitting the view/controller layer.
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        view_class = getattr(view_func, 'view_class', None)
        if not view_class:
            return None
        return validate_request_context(request, view_class, view_kwargs)
