from rest_framework.response import Response
from rest_framework import status
from typing import Any, Dict, Optional

ERROR_STATUS_MAP = {
    'NOT_FOUND': status.HTTP_404_NOT_FOUND,
    'VALIDATION_ERROR': status.HTTP_400_BAD_REQUEST,
    'UNAUTHORIZED': status.HTTP_401_UNAUTHORIZED,
    'SERVER_ERROR': status.HTTP_500_INTERNAL_SERVER_ERROR,
}

def error_response(code: str, message: str, details: Optional[Any] = None, http_status: Optional[int] = None):
    http_status = http_status or ERROR_STATUS_MAP.get(code, status.HTTP_400_BAD_REQUEST)
    payload: Dict[str, Any] = {
        'error': {
            'code': code,
            'message': message,
        }
    }
    if details is not None:
        payload['error']['details'] = details
    return Response(payload, status=http_status)
