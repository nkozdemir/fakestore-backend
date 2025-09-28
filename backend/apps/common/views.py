from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError
import time
import os

try:
    import redis as redis_lib  # optional; if unavailable we skip redis check
except ImportError:  # pragma: no cover
    redis_lib = None


def _redis_ping(url: str, timeout: float = 0.3):
    if not redis_lib:
        return {'status': 'skipped', 'detail': 'redis lib not installed'}
    try:
        client = redis_lib.from_url(url, socket_connect_timeout=timeout, socket_timeout=timeout)
        pong = client.ping()
        return {'status': 'ok' if pong else 'fail'}
    except Exception as e:  # pragma: no cover - best effort
        return {'status': 'fail', 'error': str(e)}


def _db_check(alias='default'):
    started = time.time()
    try:
        conn = connections[alias]
        conn.cursor().execute('SELECT 1')
        return {'status': 'ok', 'latency_ms': round((time.time() - started) * 1000, 2)}
    except OperationalError as e:
        return {'status': 'fail', 'error': str(e)}


def live_health(request):
    """Liveness probe: process is up and can service requests."""
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
    return JsonResponse(payload, status=http_status)
