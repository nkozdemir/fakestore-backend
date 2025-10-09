import unittest
from unittest.mock import Mock, patch
from apps.auth.services import RegistrationService


class RegistrationServiceTests(unittest.TestCase):
    def setUp(self):
        user_model = Mock()
        self.user_model_patch = patch('apps.auth.services.get_user_model', return_value=user_model)
        self.user_model_patch.start()
        self.user_model = user_model
        self.service = RegistrationService()

    def tearDown(self):
        self.user_model_patch.stop()

    def test_register_success(self):
        self.user_model.objects.filter.return_value.exists.return_value = False
        created = Mock(id=1, username='user', email='user@example.com')
        self.user_model.objects.create.return_value = created
        result = self.service.register({
            'username': 'user',
            'email': 'user@example.com',
            'password': 'x',
            'first_name': 'A',
            'last_name': 'B',
        })
        self.assertEqual(result['username'], 'user')
        self.assertEqual(result['email'], 'user@example.com')

    def test_register_duplicate_username(self):
        qs = Mock()
        qs.exists.return_value = True
        self.user_model.objects.filter.return_value = qs
        result = self.service.register({
            'username': 'dup',
            'email': 'dup@example.com',
            'password': 'x',
            'first_name': 'A',
            'last_name': 'B',
        })
        self.assertEqual(result[0], 'VALIDATION_ERROR')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
