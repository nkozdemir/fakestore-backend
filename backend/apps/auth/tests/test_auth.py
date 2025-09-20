from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from apps.users.models import User

class TestAuth(APITestCase):
    def setUp(self):
        self.register_url = reverse('auth-register')
        self.login_url = reverse('auth-login')
        self.me_url = reverse('auth-me')
        self.refresh_url = reverse('auth-refresh')
        self.logout_url = reverse('auth-logout')
        self.logout_all_url = reverse('auth-logout-all')
        self.user_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'testuser@example.com',
            'username': 'testuser',
            'password': 'TestPass123',
            'phone': '1234567890'
        }

    def test_register(self):
        response = self.client.post(self.register_url, self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='testuser').exists())

    def test_login(self):
        self.client.post(self.register_url, self.user_data, format='json')
        response = self.client.post(self.login_url, {'username': 'testuser', 'password': 'TestPass123'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_me_authenticated(self):
        self.client.post(self.register_url, self.user_data, format='json')
        login = self.client.post(self.login_url, {'username': 'testuser', 'password': 'TestPass123'}, format='json')
        token = login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')

    def test_me_unauthenticated(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token(self):
        self.client.post(self.register_url, self.user_data, format='json')
        login = self.client.post(self.login_url, {'username': 'testuser', 'password': 'TestPass123'}, format='json')
        refresh = login.data['refresh']
        response = self.client.post(self.refresh_url, {'refresh': refresh}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_logout(self):
        self.client.post(self.register_url, self.user_data, format='json')
        login = self.client.post(self.login_url, {'username': 'testuser', 'password': 'TestPass123'}, format='json')
        token = login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(self.logout_url, {'refresh': login.data['refresh']}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_all(self):
        self.client.post(self.register_url, self.user_data, format='json')
        login = self.client.post(self.login_url, {'username': 'testuser', 'password': 'TestPass123'}, format='json')
        token = login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(self.logout_all_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
