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
        self.addr_list_url = '/api/users/me/addresses/'
        self.addr_detail_url = lambda aid: f'/api/users/me/addresses/{aid}/'

    def test_list_and_create_user(self):
        res_list = self.client.get(self.list_url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        # Each user in list should include name object
        self.assertIsInstance(res_list.data, list)
        if res_list.data:
            self.assertIn('name', res_list.data[0])
            self.assertIn('firstname', res_list.data[0]['name'])
            self.assertIn('lastname', res_list.data[0]['name'])
        res_create = self.client.post(self.list_url, self.user_payload, format='json')
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_create.data['username'], self.user_payload['username'])
        # Created response should include name
        self.assertIn('name', res_create.data)
        self.assertEqual(res_create.data['name']['firstname'], self.user_payload['firstname'])
        self.assertEqual(res_create.data['name']['lastname'], self.user_payload['lastname'])

    def test_get_update_delete_user(self):
        create = self.client.post(self.list_url, self.user_payload, format='json')
        uid = create.data['id']
        res_get = self.client.get(self.detail_url(uid))
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertIn('name', res_get.data)
        self.assertEqual(res_get.data['name']['firstname'], self.user_payload['firstname'])
        self.assertEqual(res_get.data['name']['lastname'], self.user_payload['lastname'])

        put = self.client.put(self.detail_url(uid), {**self.user_payload, 'username': 'updateduser'}, format='json')
        self.assertEqual(put.status_code, status.HTTP_200_OK)
        self.assertIn('name', put.data)
        self.assertEqual(put.data['name']['firstname'], self.user_payload['firstname'])
        self.assertEqual(put.data['name']['lastname'], self.user_payload['lastname'])

        patch = self.client.patch(self.detail_url(uid), {'phone': '555-1111'}, format='json')
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertIn('name', patch.data)
        self.assertEqual(patch.data['name']['firstname'], self.user_payload['firstname'])
        self.assertEqual(patch.data['name']['lastname'], self.user_payload['lastname'])

        delete = self.client.delete(self.detail_url(uid))
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)

    def _auth(self, username='admin', password='AdminPass123'):
        login = self.client.post(reverse('auth-login'), {'username': username, 'password': password}, format='json')
        self.assertEqual(login.status_code, status.HTTP_200_OK, msg=f"Login failed for {username}: {login.content}")
        token = login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_address_crud_self_scoped(self):
        # Create user with password so we can authenticate
        payload = {**self.user_payload, 'password': 'UserPass123'}
        user_res = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(user_res.status_code, status.HTTP_201_CREATED)
        self._auth(username=payload['username'], password='UserPass123')
        address_payload = {
            'street': 'Main', 'number': 10, 'city': 'Metropolis', 'zipcode': '12345',
            'geolocation': {'lat': '1.23', 'long': '4.56'}
        }
        create_addr = self.client.post(self.addr_list_url, address_payload, format='json')
        self.assertEqual(create_addr.status_code, status.HTTP_201_CREATED)
        aid = create_addr.data['id']
        list_addr = self.client.get(self.addr_list_url)
        self.assertEqual(list_addr.status_code, status.HTTP_200_OK)
        self.assertTrue(any(a['id'] == aid for a in list_addr.data))
        get_addr = self.client.get(self.addr_detail_url(aid))
        self.assertEqual(get_addr.status_code, status.HTTP_200_OK)
        patch_addr = self.client.patch(self.addr_detail_url(aid), {'city': 'Gotham'}, format='json')
        self.assertEqual(patch_addr.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_addr.data['city'], 'Gotham')
        del_addr = self.client.delete(self.addr_detail_url(aid))
        self.assertEqual(del_addr.status_code, status.HTTP_204_NO_CONTENT)
        get_after_delete = self.client.get(self.addr_detail_url(aid))
        self.assertEqual(get_after_delete.status_code, status.HTTP_404_NOT_FOUND)

    def test_address_access_denied_other_user(self):
        # User A with password
        user_a_payload = {**self.user_payload, 'username': 'userA', 'email': 'userA@example.com', 'password': 'AAApass123'}
        a_res = self.client.post(self.list_url, user_a_payload, format='json')
        self.assertEqual(a_res.status_code, status.HTTP_201_CREATED)
        self._auth(username='userA', password='AAApass123')
        addr_payload = {
            'street': 'First', 'number': 1, 'city': 'CityA', 'zipcode': '00001',
            'geolocation': {'lat': '0', 'long': '0'}
        }
        create_addr_a = self.client.post(self.addr_list_url, addr_payload, format='json')
        self.assertEqual(create_addr_a.status_code, status.HTTP_201_CREATED)
        aid = create_addr_a.data['id']
        # User B
        user_b_payload = {**self.user_payload, 'username': 'userB', 'email': 'userB@example.com', 'password': 'BBBpass123', 'id': 11}
        b_res = self.client.post(self.list_url, user_b_payload, format='json')
        self.assertEqual(b_res.status_code, status.HTTP_201_CREATED)
        self._auth(username='userB', password='BBBpass123')
        get_other = self.client.get(self.addr_detail_url(aid))
        self.assertEqual(get_other.status_code, status.HTTP_404_NOT_FOUND)
        patch_other = self.client.patch(self.addr_detail_url(aid), {'city': 'HackCity'}, format='json')
        self.assertEqual(patch_other.status_code, status.HTTP_404_NOT_FOUND)
        del_other = self.client.delete(self.addr_detail_url(aid))
        self.assertEqual(del_other.status_code, status.HTTP_404_NOT_FOUND)
