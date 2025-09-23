from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from apps.users.models import User
from apps.catalog.models import Product, Category
from apps.carts.models import Cart, CartProduct

class TestCarts(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='cartuser', password='TestPass123', firstname='Cart', lastname='User', email='cart@example.com'
        )
        self.list_url = reverse('api-carts-list') if False else '/api/carts/'
        self.detail_url = lambda cid: f'/api/carts/{cid}/'

        # Seed one product & category for patch ops
        self.cat = Category.objects.create(name='Gadgets')
        self.product = Product.objects.create(id=101, title='Widget', price=10.00, description='w', image='', rate=0, count=0)
        self.product.categories.add(self.cat)

    def _auth(self):
        login = self.client.post(reverse('auth-login'), {'username': 'cartuser', 'password': 'TestPass123'}, format='json')
        token = login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_create_and_get_cart(self):
        self._auth()
        # New contract: user is inferred from JWT; optional products list
        payload = {
            'products': [
                {'productId': self.product.id, 'quantity': 2}
            ]
        }
        res = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        cid = res.data['id']
        res_get = self.client.get(self.detail_url(cid))
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data['id'], cid)

    def test_patch_cart_operations(self):
        self._auth()
        # Create empty cart first (id auto-assigned); user inferred from JWT
        create = self.client.post(self.list_url, {}, format='json')
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        cid = create.data['id']
        # Add
        patch1 = self.client.patch(self.detail_url(cid), {
            'add': [
                {'productId': self.product.id, 'quantity': 3}
            ]
        }, format='json')
        self.assertEqual(patch1.status_code, status.HTTP_200_OK)
        # Update
        patch2 = self.client.patch(self.detail_url(cid), {
            'update': [
                {'productId': self.product.id, 'quantity': 1}
            ]
        }, format='json')
        self.assertEqual(patch2.status_code, status.HTTP_200_OK)
        # Remove
        patch3 = self.client.patch(self.detail_url(cid), {
            'remove': [self.product.id]
        }, format='json')
        self.assertEqual(patch3.status_code, status.HTTP_200_OK)

    def test_update_and_delete_cart(self):
        self._auth()
        create = self.client.post(self.list_url, {}, format='json')
        cid = create.data['id']
        put = self.client.put(self.detail_url(cid), {'id': cid, 'user_id': self.user.id, 'date': '2025-09-18T00:00:00Z', 'items': []}, format='json')
        self.assertEqual(put.status_code, status.HTTP_200_OK)
        delete = self.client.delete(self.detail_url(cid))
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        # Verify it cannot be retrieved anymore
        get_after_delete = self.client.get(self.detail_url(cid))
        self.assertEqual(get_after_delete.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_denied_for_non_owner(self):
        # User1 creates a cart
        self._auth()  # auth as self.user
        create = self.client.post(self.list_url, {}, format='json')
        cid = create.data['id']

        # Create another user and auth as them
        other = User.objects.create_user(
            username='cartuser2', password='TestPass123', firstname='Other', lastname='User', email='cart2@example.com'
        )
        login2 = self.client.post(reverse('auth-login'), {'username': 'cartuser2', 'password': 'TestPass123'}, format='json')
        token2 = login2.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token2}')

        # Attempt delete as non-owner should return 404 (not found/forbidden by scoping)
        resp = self.client.delete(self.detail_url(cid))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
