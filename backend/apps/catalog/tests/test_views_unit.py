import types
import unittest
from decimal import Decimal
from unittest.mock import Mock, patch
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.permissions import AllowAny
from apps.catalog.views import (
    ProductListView,
    ProductDetailView,
    ProductRatingView,
    CategoryListView,
    CategoryDetailView,
    ProductByCategoriesView,
)
from apps.catalog.dtos import ProductDTO, CategoryDTO


def make_product_dto(product_id=1, title='Widget'):
    category = CategoryDTO(id=1, name='Electronics')
    return ProductDTO(
        id=product_id,
        title=title,
        price='10.00',
        description='A product',
        image='img',
        rate='4.5',
        count=2,
        categories=[category],
    )

def make_category_dto(category_id=1, name='Cat'):
    return CategoryDTO(id=category_id, name=name)


class CatalogViewsUnitTests(unittest.TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_product_list_paginates_and_filters(self):
        dto1 = make_product_dto(1)
        dto2 = make_product_dto(2, title='Gadget')
        service_mock = Mock()
        service_mock.list_products.return_value = [dto1, dto2]
        with patch.object(ProductListView, 'service', service_mock):
            request = self.factory.get('/api/products/', {'limit': 1, 'category': 'electronics'})
            response = ProductListView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), 1)
        service_mock.list_products.assert_called_once_with(category='electronics')

    def test_product_list_post_creates_product(self):
        dto = make_product_dto(3, 'Created')
        service_mock = Mock()
        service_mock.create_product.return_value = dto
        payload = {
            'title': 'Created',
            'price': '12.50',
            'description': 'New item',
            'image': 'img',
        }
        user = types.SimpleNamespace(id=1, is_authenticated=True)
        with patch.object(ProductListView, 'service', service_mock):
            request = self.factory.post('/api/products/', payload, format='json')
            force_authenticate(request, user=user)
            response = ProductListView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['title'], 'Created')
        args, kwargs = service_mock.create_product.call_args
        self.assertEqual(args[0]['title'], 'Created')
        self.assertEqual(args[0]['price'], Decimal('12.50'))

    def test_product_detail_get_not_found(self):
        service_mock = Mock()
        service_mock.get_product.return_value = None
        with patch.object(ProductDetailView, 'service', service_mock):
            request = self.factory.get('/api/products/10/')
            response = ProductDetailView.as_view()(request, product_id=10)
        response.render()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')

    def test_product_detail_get_success(self):
        dto = make_product_dto(5, 'LookUp')
        service_mock = Mock()
        service_mock.get_product.return_value = dto
        with patch.object(ProductDetailView, 'service', service_mock):
            request = self.factory.get('/api/products/5/')
            response = ProductDetailView.as_view()(request, product_id=5)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'LookUp')

    def test_product_detail_put_not_found(self):
        service_mock = Mock()
        service_mock.update_product.return_value = None
        payload = {
            'title': 'Updated',
            'price': '20.00',
            'description': 'Desc',
            'image': 'img',
        }
        user = types.SimpleNamespace(id=2, is_authenticated=True)
        with patch.object(ProductDetailView, 'service', service_mock):
            request = self.factory.put('/api/products/1/', payload, format='json')
            force_authenticate(request, user=user)
            response = ProductDetailView.as_view()(request, product_id=1)
        response.render()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')

    def test_product_detail_delete_success(self):
        service_mock = Mock()
        service_mock.delete_product.return_value = True
        user = types.SimpleNamespace(id=3, is_authenticated=True)
        with patch.object(ProductDetailView, 'service', service_mock):
            request = self.factory.delete('/api/products/2/')
            force_authenticate(request, user=user)
            response = ProductDetailView.as_view()(request, product_id=2)
        response.render()
        self.assertEqual(response.status_code, 204)

    def test_product_detail_delete_not_found(self):
        service_mock = Mock()
        service_mock.delete_product.return_value = False
        user = types.SimpleNamespace(id=9, is_authenticated=True)
        with patch.object(ProductDetailView, 'service', service_mock):
            request = self.factory.delete('/api/products/8/')
            force_authenticate(request, user=user)
            response = ProductDetailView.as_view()(request, product_id=8)
        response.render()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['detail'], 'Not found')

    def test_product_detail_patch_returns_404_when_missing(self):
        service_mock = Mock()
        service_mock.get_product.return_value = None
        user = types.SimpleNamespace(id=4, is_authenticated=True)
        with patch.object(ProductDetailView, 'service', service_mock):
            request = self.factory.patch('/api/products/3/', {'title': 'New'}, format='json')
            force_authenticate(request, user=user)
            response = ProductDetailView.as_view()(request, product_id=3)
        response.render()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['detail'], 'Not found')

    def test_product_detail_put_success(self):
        dto = make_product_dto(6, 'Updated')
        service_mock = Mock()
        service_mock.update_product.return_value = dto
        payload = {
            'title': 'Updated',
            'price': '15.00',
            'description': 'Desc',
            'image': 'img',
        }
        user = types.SimpleNamespace(id=11, is_authenticated=True)
        with patch.object(ProductDetailView, 'service', service_mock):
            request = self.factory.put('/api/products/6/', payload, format='json')
            force_authenticate(request, user=user)
            response = ProductDetailView.as_view()(request, product_id=6)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'Updated')

    def test_product_detail_patch_success(self):
        original = make_product_dto(7, 'Original')
        updated = make_product_dto(7, 'Patched')
        service_mock = Mock()
        service_mock.get_product.return_value = original
        service_mock.update_product.return_value = updated
        user = types.SimpleNamespace(id=12, is_authenticated=True)
        with patch.object(ProductDetailView, 'service', service_mock):
            request = self.factory.patch('/api/products/7/', {'title': 'Patched'}, format='json')
            force_authenticate(request, user=user)
            response = ProductDetailView.as_view()(request, product_id=7)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'Patched')

    def test_category_list_get_and_post(self):
        categories = [make_category_dto(1, 'A')]
        created = make_category_dto(2, 'B')
        service_mock = Mock()
        service_mock.list_categories.return_value = categories
        service_mock.create_category.return_value = created
        user = types.SimpleNamespace(id=20, is_authenticated=True)
        with patch.object(CategoryListView, 'service', service_mock):
            request_get = self.factory.get('/api/categories/')
            response_get = CategoryListView.as_view()(request_get)
        response_get.render()
        self.assertEqual(response_get.status_code, 200)
        self.assertEqual(response_get.data[0]['name'], 'A')

        with patch.object(CategoryListView, 'service', service_mock):
            request_post = self.factory.post('/api/categories/', {'name': 'B'}, format='json')
            force_authenticate(request_post, user=user)
            response_post = CategoryListView.as_view()(request_post)
        response_post.render()
        self.assertEqual(response_post.status_code, 201)
        self.assertEqual(response_post.data['name'], 'B')

    def test_category_detail_get_and_not_found(self):
        service_mock = Mock()
        service_mock.get_category.side_effect = [make_category_dto(3, 'Found'), None]
        with patch.object(CategoryDetailView, 'service', service_mock):
            request_get = self.factory.get('/api/categories/3/')
            response_get = CategoryDetailView.as_view()(request_get, category_id=3)
        response_get.render()
        self.assertEqual(response_get.status_code, 200)
        self.assertEqual(response_get.data['name'], 'Found')

        with patch.object(CategoryDetailView, 'service', service_mock):
            request_missing = self.factory.get('/api/categories/4/')
            response_missing = CategoryDetailView.as_view()(request_missing, category_id=4)
        response_missing.render()
        self.assertEqual(response_missing.status_code, 404)
        self.assertEqual(response_missing.data['error']['code'], 'NOT_FOUND')

    def test_category_detail_put_patch_and_delete(self):
        service_mock = Mock()
        service_mock.update_category.side_effect = [
            make_category_dto(5, 'Updated'),
            None,
            make_category_dto(5, 'Patched'),
        ]
        service_mock.delete_category.side_effect = [False, True]
        user = types.SimpleNamespace(id=30, is_authenticated=True)

        with patch.object(CategoryDetailView, 'service', service_mock):
            request_put = self.factory.put('/api/categories/5/', {'name': 'Updated'}, format='json')
            force_authenticate(request_put, user=user)
            response_put = CategoryDetailView.as_view()(request_put, category_id=5)
        response_put.render()
        self.assertEqual(response_put.status_code, 200)
        self.assertEqual(response_put.data['name'], 'Updated')

        with patch.object(CategoryDetailView, 'service', service_mock):
            request_patch_missing = self.factory.patch('/api/categories/5/', {'name': 'Missing'}, format='json')
            force_authenticate(request_patch_missing, user=user)
            response_patch_missing = CategoryDetailView.as_view()(request_patch_missing, category_id=5)
        response_patch_missing.render()
        self.assertEqual(response_patch_missing.status_code, 404)
        self.assertEqual(response_patch_missing.data['error']['code'], 'NOT_FOUND')

        with patch.object(CategoryDetailView, 'service', service_mock):
            request_patch = self.factory.patch('/api/categories/5/', {'name': 'Patched'}, format='json')
            force_authenticate(request_patch, user=user)
            response_patch = CategoryDetailView.as_view()(request_patch, category_id=5)
        response_patch.render()
        self.assertEqual(response_patch.status_code, 200)
        self.assertEqual(response_patch.data['name'], 'Patched')

        with patch.object(CategoryDetailView, 'service', service_mock):
            request_delete_missing = self.factory.delete('/api/categories/5/')
            force_authenticate(request_delete_missing, user=user)
            response_delete_missing = CategoryDetailView.as_view()(request_delete_missing, category_id=5)
        response_delete_missing.render()
        self.assertEqual(response_delete_missing.status_code, 404)
        self.assertEqual(response_delete_missing.data['error']['code'], 'NOT_FOUND')

        with patch.object(CategoryDetailView, 'service', service_mock):
            request_delete = self.factory.delete('/api/categories/5/')
            force_authenticate(request_delete, user=user)
            response_delete = CategoryDetailView.as_view()(request_delete, category_id=5)
        response_delete.render()
        self.assertEqual(response_delete.status_code, 204)

    def test_category_detail_put_not_found(self):
        service_mock = Mock()
        service_mock.update_category.return_value = None
        user = types.SimpleNamespace(id=31, is_authenticated=True)
        with patch.object(CategoryDetailView, 'service', service_mock):
            request_put = self.factory.put('/api/categories/9/', {'name': 'Missing'}, format='json')
            force_authenticate(request_put, user=user)
            response_put = CategoryDetailView.as_view()(request_put, category_id=9)
        response_put.render()
        self.assertEqual(response_put.status_code, 404)
        self.assertEqual(response_put.data['error']['code'], 'NOT_FOUND')

    def test_product_rating_post_requires_user_id(self):
        service_mock = Mock()
        user = types.SimpleNamespace(id=None, is_authenticated=True)
        with patch.object(ProductRatingView, 'service', service_mock):
            request = self.factory.post('/api/products/1/rating/', {'value': 3}, format='json')
            force_authenticate(request, user=user)
            response = ProductRatingView.as_view()(request, product_id=1)
        response.render()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')
        service_mock.set_user_rating.assert_not_called()

    def test_product_rating_post_handles_service_error(self):
        service_mock = Mock()
        service_mock.set_user_rating.return_value = ('NOT_FOUND', 'missing', {'id': 1})
        user = types.SimpleNamespace(id=7, is_authenticated=True)
        with patch.object(ProductRatingView, 'service', service_mock):
            request = self.factory.post('/api/products/1/rating/', {'value': 4}, format='json')
            force_authenticate(request, user=user)
            response = ProductRatingView.as_view()(request, product_id=1)
        response.render()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')

    def test_product_rating_post_validates_value(self):
        service_mock = Mock()
        user = types.SimpleNamespace(id=5, is_authenticated=True)
        with patch.object(ProductRatingView, 'service', service_mock):
            request = self.factory.post('/api/products/1/rating/', {'value': 'bad'}, format='json')
            force_authenticate(request, user=user)
            response = ProductRatingView.as_view()(request, product_id=1)
        response.render()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')
        service_mock.set_user_rating.assert_not_called()

    def test_product_rating_get_not_found(self):
        service_mock = Mock()
        service_mock.get_rating_summary.return_value = None
        request = self.factory.get('/api/products/1/rating/')
        with patch.object(ProductRatingView, 'service', service_mock):
            response = ProductRatingView.as_view()(request, product_id=1)
        response.render()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')

    def test_product_rating_get_header_fallback(self):
        service_mock = Mock()
        service_mock.get_rating_summary.return_value = {'rating': {'rate': 5, 'count': 1}}
        request = self.factory.get('/api/products/1/rating/', HTTP_X_USER_ID='42')
        with patch.object(ProductRatingView, 'service', service_mock):
            response = ProductRatingView.as_view()(request, product_id=1)
        response.render()
        self.assertEqual(response.status_code, 200)
        service_mock.get_rating_summary.assert_called_once_with(1, 42)

    def test_product_rating_post_header_and_query_fallback(self):
        service_mock = Mock()
        service_mock.set_user_rating.return_value = {'rating': {'rate': 4, 'count': 1}}
        request = self.factory.post('/api/products/1/rating/?userId=55', {'value': 4}, format='json')
        with patch.object(ProductRatingView, 'service', service_mock), \
             patch.object(ProductRatingView, 'permission_classes', [AllowAny]):
            response = ProductRatingView.as_view()(request, product_id=1)
        response.render()
        self.assertEqual(response.status_code, 201)
        service_mock.set_user_rating.assert_called_once_with(1, 55, 4)

    def test_product_rating_post_invalid_header_value(self):
        service_mock = Mock()
        request = self.factory.post('/api/products/1/rating/', {'value': 4}, format='json', HTTP_X_USER_ID='bad')
        with patch.object(ProductRatingView, 'service', service_mock), \
             patch.object(ProductRatingView, 'permission_classes', [AllowAny]):
            response = ProductRatingView.as_view()(request, product_id=1)
        response.render()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')
        service_mock.set_user_rating.assert_not_called()

    def test_product_rating_delete_success_and_error(self):
        service_mock = Mock()
        service_mock.delete_user_rating.side_effect = [
            {'rating': {'rate': 0, 'count': 0}},
            ('NOT_FOUND', 'missing', {'id': 1}),
        ]
        request_success = self.factory.delete('/api/products/1/rating/', HTTP_X_USER_ID='77')
        with patch.object(ProductRatingView, 'service', service_mock), \
             patch.object(ProductRatingView, 'permission_classes', [AllowAny]):
            response_success = ProductRatingView.as_view()(request_success, product_id=1)
        response_success.render()
        self.assertEqual(response_success.status_code, 200)
        self.assertEqual(response_success.data['rating']['count'], 0)

        request_error = self.factory.delete('/api/products/1/rating/', HTTP_X_USER_ID='77')
        with patch.object(ProductRatingView, 'service', service_mock), \
             patch.object(ProductRatingView, 'permission_classes', [AllowAny]):
            response_error = ProductRatingView.as_view()(request_error, product_id=1)
        response_error.render()
        self.assertEqual(response_error.status_code, 404)
        self.assertEqual(response_error.data['error']['code'], 'NOT_FOUND')

    def test_product_rating_delete_requires_user(self):
        service_mock = Mock()
        user = types.SimpleNamespace(id=None, is_authenticated=True)
        request = self.factory.delete('/api/products/1/rating/')
        force_authenticate(request, user=user)
        with patch.object(ProductRatingView, 'service', service_mock):
            response = ProductRatingView.as_view()(request, product_id=1)
        response.render()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')

    def test_product_by_categories_view(self):
        products = [make_product_dto(1)]
        service_mock = Mock()
        service_mock.list_products_by_category_ids.return_value = products

        with patch.object(ProductByCategoriesView, 'service', service_mock):
            request_missing = self.factory.get('/api/products/by-categories/')
            response_missing = ProductByCategoriesView.as_view()(request_missing)
        response_missing.render()
        self.assertEqual(response_missing.status_code, 200)
        self.assertEqual(response_missing.data, [])

        with patch.object(ProductByCategoriesView, 'service', service_mock):
            request_invalid = self.factory.get('/api/products/by-categories/', {'categoryIds': 'a,b'})
            response_invalid = ProductByCategoriesView.as_view()(request_invalid)
        response_invalid.render()
        self.assertEqual(response_invalid.status_code, 400)
        self.assertEqual(response_invalid.data['error']['code'], 'VALIDATION_ERROR')

        with patch.object(ProductByCategoriesView, 'service', service_mock):
            request_empty = self.factory.get('/api/products/by-categories/', {'categoryIds': ' , '})
            response_empty = ProductByCategoriesView.as_view()(request_empty)
        response_empty.render()
        self.assertEqual(response_empty.status_code, 200)
        self.assertEqual(response_empty.data, [])

        with patch.object(ProductByCategoriesView, 'service', service_mock):
            request_valid = self.factory.get('/api/products/by-categories/', {'categoryIds': '1, 2'})
            response_valid = ProductByCategoriesView.as_view()(request_valid)
        response_valid.render()
        self.assertEqual(response_valid.status_code, 200)
        service_mock.list_products_by_category_ids.assert_called_once_with([1, 2])
