import unittest
from rest_framework import status
from apps.api.utils import error_response


class ErrorResponseTests(unittest.TestCase):
    def test_default_status_mapping_and_details(self):
        resp = error_response('NOT_FOUND', 'missing', {'id': 1})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data['error']['code'], 'NOT_FOUND')
        self.assertEqual(resp.data['error']['details'], {'id': 1})

    def test_custom_status_override(self):
        resp = error_response('UNKNOWN', 'oops', http_status=status.HTTP_202_ACCEPTED)
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(resp.data['error']['message'], 'oops')
