from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError
import time
import os
from .logger import get_logger

try:
    import redis as redis_lib  # optional; if unavailable we skip redis check
except ImportError:  # pragma: no cover
    redis_lib = None

logger = get_logger(__name__).bind(component='common', layer='health')


def _redis_ping(url: str, timeout: float = 0.3):
    if not redis_lib:
        logger.debug('Redis health check skipped; library missing')
        return {'status': 'skipped', 'detail': 'redis lib not installed'}
    try:
        client = redis_lib.from_url(url, socket_connect_timeout=timeout, socket_timeout=timeout)
        pong = client.ping()
        result = {'status': 'ok' if pong else 'fail'}
        if result['status'] == 'ok':
            logger.debug('Redis health check succeeded')
        else:
            logger.warning('Redis health check returned unexpected response')
        return result
    except Exception as e:  # pragma: no cover - best effort
        logger.warning('Redis health check failed', error=str(e))
        return {'status': 'fail', 'error': str(e)}


def _db_check(alias='default'):
    started = time.time()
    try:
        conn = connections[alias]
        conn.cursor().execute('SELECT 1')
        latency = round((time.time() - started) * 1000, 2)
        logger.debug('Database health check succeeded', alias=alias, latency_ms=latency)
        return {'status': 'ok', 'latency_ms': latency}
    except OperationalError as e:
        # Expected operational DB issues (connection refused, etc.)
        logger.warning('Database health check encountered operational error', alias=alias, error=str(e))
        return {'status': 'fail', 'error': str(e)}
    except Exception as e:  # broaden for unexpected exceptions (mocked failures, driver bugs)
        logger.error('Database health check failed unexpectedly', alias=alias, error=str(e), exception=e.__class__.__name__)
        return {'status': 'fail', 'error': str(e), 'exception': e.__class__.__name__}


def live_health(request):
    """Liveness probe: process is up and can service requests."""
    logger.debug('Liveness probe served')
    return JsonResponse({'status': 'alive'})


def ready_health(request):
    """Readiness probe: verifies critical dependencies (DB, Redis)."""
    checks = {}
    db_result = _db_check()
    checks['database'] = db_result

    redis_url = os.getenv('REDIS_URL')
    if redis_url:
        checks['redis'] = _redis_ping(redis_url)
    else:
        checks['redis'] = {'status': 'skipped', 'detail': 'REDIS_URL not set'}

    failing = [name for name, r in checks.items() if r.get('status') == 'fail']
    overall_status = 'ok' if not failing else 'degraded'
    http_status = 200 if not failing else 503
    payload = {
        'status': overall_status,
        'checks': checks,
    }
    logger.info('Readiness probe evaluated', status=overall_status, failing_components=failing)
    return JsonResponse(payload, status=http_status)
