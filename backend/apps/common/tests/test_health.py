from django.test import TestCase, override_settings
from django.urls import reverse
from unittest import mock


class HealthEndpointsTests(TestCase):
    def test_live_health(self):
        resp = self.client.get('/health/live')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get('status'), 'alive')

    def test_ready_health_ok(self):
        resp = self.client.get('/health/ready')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('checks', data)
        self.assertEqual(data['status'], 'ok')  # DB should respond in test

    @mock.patch('apps.common.views.connections')
    def test_ready_health_db_failure(self, mock_connections):
        class DummyConn:
            def cursor(self):
                class C:  # noqa: D401
                    def execute(self, *_args, **_kwargs):
                        raise Exception('db down')
                return C()
        mock_connections.__getitem__.return_value = DummyConn()
        resp = self.client.get('/health/ready')
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()['status'], 'degraded')
