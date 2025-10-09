import json
import unittest
from unittest import mock
from apps.common import views


class HealthViewsUnitTests(unittest.TestCase):
    def test_live_health_returns_alive_payload(self):
        response = views.live_health(None)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload['status'], 'alive')

    @mock.patch('apps.common.views.os.getenv', return_value=None)
    @mock.patch('apps.common.views._db_check', return_value={'status': 'ok', 'latency_ms': 1.23})
    def test_ready_health_ok_when_dependencies_pass(self, mock_db_check, _mock_getenv):
        response = views.ready_health(None)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['checks']['database'], mock_db_check.return_value)
        self.assertEqual(payload['checks']['redis']['status'], 'skipped')

    @mock.patch('apps.common.views.os.getenv', return_value='redis://localhost')
    @mock.patch('apps.common.views._redis_ping', return_value={'status': 'fail', 'error': 'unreachable'})
    @mock.patch('apps.common.views._db_check', return_value={'status': 'fail', 'error': 'db down'})
    def test_ready_health_degraded_on_dependency_failure(self, mock_db_check, mock_redis_ping, _mock_getenv):
        response = views.ready_health(None)
        self.assertEqual(response.status_code, 503)
        payload = json.loads(response.content)
        self.assertEqual(payload['status'], 'degraded')
        self.assertEqual(payload['checks']['database'], mock_db_check.return_value)
        self.assertEqual(payload['checks']['redis'], mock_redis_ping.return_value)
