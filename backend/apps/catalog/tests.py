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

    def test_list_products_filter_by_category(self):
        # Create category and assign to product
        c = Category.objects.create(name='Electronics')
        p = Product.objects.create(**self.product_data)
        p.categories.add(c)
        # Matching filter
        res1 = self.client.get(self.product_url + '?category=Electronics')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertTrue(any(item['id'] == p.id for item in res1.data))
        # Non-matching filter
        res2 = self.client.get(self.product_url + '?category=Books')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res2.data), 0)

    def test_products_by_categories_endpoint(self):
        c1 = Category.objects.create(name='A')
        c2 = Category.objects.create(name='B')
        p1 = Product.objects.create(id=2, title='P2', price=50.00, description='d', image='', rate=0, count=0)
        p2 = Product.objects.create(id=3, title='P3', price=60.00, description='d', image='', rate=0, count=0)
        p1.categories.add(c1)
        p2.categories.add(c2)
        # both categories
        res = self.client.get(reverse('api-products-by-categories') + f'?categoryIds={c1.id},{c2.id}')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = {item['id'] for item in res.data}
        self.assertTrue({p1.id, p2.id}.issubset(ids))
        # empty param
        res_empty = self.client.get(reverse('api-products-by-categories'))
        self.assertEqual(res_empty.status_code, status.HTTP_200_OK)
        self.assertEqual(res_empty.data, [])
        # invalid param
        res_invalid = self.client.get(reverse('api-products-by-categories') + '?categoryIds=a,b')
        self.assertEqual(res_invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', res_invalid.data)

    def test_error_envelope_not_found(self):
        # product not found
        res_p = self.client.get(reverse('api-products-detail', args=[9999]))
        self.assertEqual(res_p.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', res_p.data)
        self.assertEqual(res_p.data['error']['code'], 'NOT_FOUND')
        # category not found
        res_c = self.client.get(reverse('api-categories-detail', args=[9999]))
        self.assertEqual(res_c.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', res_c.data)
        self.assertEqual(res_c.data['error']['code'], 'NOT_FOUND')
