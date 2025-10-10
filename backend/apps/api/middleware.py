from django.utils.deprecation import MiddlewareMixin
from apps.api.validation import validate_request_context
from apps.common import get_logger

logger = get_logger(__name__).bind(component='api', layer='middleware')


class RequestValidationMiddleware(MiddlewareMixin):
    """
    Centralised request validation middleware that ensures authentication- and
    query-related checks are executed before hitting the view/controller layer.
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        view_class = getattr(view_func, 'view_class', None)
        if not view_class:
            return None
        view_name = getattr(view_class, '__name__', str(view_class))
        logger.debug('Validating request context', view=view_name, method=getattr(request, 'method', None))
        response = validate_request_context(request, view_class, view_kwargs)
        if response is not None:
            logger.info(
                'Request blocked by validation',
                view=view_name,
                method=getattr(request, 'method', None),
                status=getattr(response, 'status_code', None),
            )
        return response
