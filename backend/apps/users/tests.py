from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from apps.users.models import User

class TestUsers(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin', password='AdminPass123', firstname='Admin', lastname='User', email='admin@example.com', is_staff=True)
        self.user_payload = {
            'id': 10,
            'username': 'newuser',
            'email': 'new@example.com',
            'firstname': 'New',
            'lastname': 'User',
            'phone': '555-0000'
        }
        self.list_url = '/api/users/'
        self.detail_url = lambda uid: f'/api/users/{uid}/'

    def test_list_and_create_user(self):
        res_list = self.client.get(self.list_url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        res_create = self.client.post(self.list_url, self.user_payload, format='json')
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_create.data['username'], self.user_payload['username'])

    def test_get_update_delete_user(self):
        create = self.client.post(self.list_url, self.user_payload, format='json')
        uid = create.data['id']
        res_get = self.client.get(self.detail_url(uid))
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        put = self.client.put(self.detail_url(uid), {**self.user_payload, 'username': 'updateduser'}, format='json')
        self.assertEqual(put.status_code, status.HTTP_200_OK)
        patch = self.client.patch(self.detail_url(uid), {'phone': '555-1111'}, format='json')
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        delete = self.client.delete(self.detail_url(uid))
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
