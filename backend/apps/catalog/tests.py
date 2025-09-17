from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from apps.users.models import User
from apps.catalog.models import Product, Category

class TestProductCategoryRating(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='TestPass123', firstname='Test', lastname='User', email='testuser@example.com', phone='1234567890'
        )
        self.product_data = {
            'id': 1,
            'title': 'Test Product',
            'price': 99.99,
            'description': 'A test product',
            'image': '',
            'rate': 0,
            'count': 0
        }
        self.category_data = {'name': 'Test Category'}
        self.product_url = reverse('api-products-list')
        self.category_url = reverse('api-categories-list')

    def authenticate(self):
        login = self.client.post(reverse('auth-login'), {'username': 'testuser', 'password': 'TestPass123'}, format='json')
        token = login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_create_product(self):
        self.authenticate()
        response = self.client.post(self.product_url, self.product_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Test Product')

    def test_list_products(self):
        Product.objects.create(**self.product_data)
        response = self.client.get(self.product_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) >= 1)

    def test_get_product_detail(self):
        product = Product.objects.create(**self.product_data)
        url = reverse('api-products-detail', args=[product.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Test Product')

    def test_update_product(self):
        product = Product.objects.create(**self.product_data)
        url = reverse('api-products-detail', args=[product.id])
        self.authenticate()
        response = self.client.put(url, {**self.product_data, 'title': 'Updated Product'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated Product')

    def test_delete_product(self):
        product = Product.objects.create(**self.product_data)
        url = reverse('api-products-detail', args=[product.id])
        self.authenticate()
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_create_category(self):
        self.authenticate()
        response = self.client.post(self.category_url, self.category_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Test Category')

    def test_list_categories(self):
        Category.objects.create(**self.category_data)
        response = self.client.get(self.category_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) >= 1)

    def test_get_category_detail(self):
        category = Category.objects.create(**self.category_data)
        url = reverse('api-categories-detail', args=[category.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Category')

    def test_update_category(self):
        category = Category.objects.create(**self.category_data)
        url = reverse('api-categories-detail', args=[category.id])
        self.authenticate()
        response = self.client.put(url, {'name': 'Updated Category'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Category')

    def test_delete_category(self):
        category = Category.objects.create(**self.category_data)
        url = reverse('api-categories-detail', args=[category.id])
        self.authenticate()
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_get_product_rating(self):
        product = Product.objects.create(**self.product_data)
        url = reverse('api-products-rating', args=[product.id])
        self.authenticate()
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('rating', response.data)

    def test_set_product_rating(self):
        product = Product.objects.create(**self.product_data)
        url = reverse('api-products-rating', args=[product.id])
        self.authenticate()
        response = self.client.post(url, {'value': 4}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['userRating'], 4)

    def test_delete_product_rating(self):
        product = Product.objects.create(**self.product_data)
        url = reverse('api-products-rating', args=[product.id])
        self.authenticate()
        self.client.post(url, {'value': 5}, format='json')
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['userRating'])
