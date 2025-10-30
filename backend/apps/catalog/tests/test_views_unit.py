import types
import unittest
from decimal import Decimal
from unittest.mock import Mock, patch
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.response import Response
from apps.catalog.views import (
    ProductListView,
    ProductDetailView,
    ProductRatingListView,
    ProductRatingView,
    CategoryListView,
    CategoryDetailView,
)
from apps.catalog.pagination import ProductListPagination
from apps.catalog.serializers import ProductReadSerializer
from apps.catalog.dtos import ProductDTO, CategoryDTO
from apps.api.validation import validate_request_context


def make_product_dto(product_id=1, title="Widget"):
    category = CategoryDTO(id=1, name="Electronics")
    return ProductDTO(
        id=product_id,
        title=title,
        price="10.00",
        description="A product",
        image="img",
        rate="4.5",
        count=2,
        categories=[category],
    )


def make_category_dto(category_id=1, name="Cat"):
    return CategoryDTO(id=category_id, name=name)


class CatalogViewsUnitTests(unittest.TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def dispatch(self, request, view_cls, **kwargs):
        pre_response = validate_request_context(request, view_cls, kwargs)
        if pre_response is not None:
            return pre_response
        view = view_cls.as_view()
        return view(request, **kwargs)

    def authenticate(self, request, user):
        request.user = user
        force_authenticate(request, user=user)

    def test_product_list_paginates_and_filters(self):
        service_mock = Mock()
        expected_response = Response({"results": []})
        service_mock.list_products_paginated.return_value = expected_response
        with patch.object(ProductListView, "service", service_mock):
            request = self.factory.get(
                "/api/products/", {"limit": 1, "category": "electronics"}
            )
            response = self.dispatch(request, ProductListView)
        self.assertIs(response, expected_response)
        service_mock.list_products_paginated.assert_called_once()
        _, kwargs = service_mock.list_products_paginated.call_args
        self.assertEqual(kwargs["category"], "electronics")
        self.assertIs(kwargs["paginator_class"], ProductListPagination)
        self.assertIs(kwargs["serializer_class"], ProductReadSerializer)
        self.assertEqual(kwargs["view"].__class__, ProductListView)

    def test_product_list_post_creates_product(self):
        dto = make_product_dto(3, "Created")
        service_mock = Mock()
        service_mock.create_product.return_value = dto
        payload = {
            "title": "Created",
            "price": "12.50",
            "description": "New item",
            "image": "img",
        }
        user = types.SimpleNamespace(
            id=1, is_authenticated=True, is_staff=True, is_superuser=False
        )
        with patch.object(ProductListView, "service", service_mock):
            request = self.factory.post("/api/products/", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, ProductListView)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["title"], "Created")
        args, kwargs = service_mock.create_product.call_args
        self.assertEqual(args[0]["title"], "Created")
        self.assertEqual(args[0]["price"], Decimal("12.50"))

    def test_product_list_post_forbidden_for_non_admin(self):
        service_mock = Mock()
        payload = {
            "title": "Created",
            "price": "12.50",
            "description": "New item",
            "image": "img",
        }
        user = types.SimpleNamespace(
            id=50, is_authenticated=True, is_staff=False, is_superuser=False
        )
        with patch.object(ProductListView, "service", service_mock):
            request = self.factory.post("/api/products/", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, ProductListView)
        self.assertEqual(response.status_code, 403)
        service_mock.create_product.assert_not_called()

    def test_product_detail_get_not_found(self):
        service_mock = Mock()
        service_mock.get_product.return_value = None
        with patch.object(ProductDetailView, "service", service_mock):
            request = self.factory.get("/api/products/10/")
            response = self.dispatch(request, ProductDetailView, product_id=10)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"]["code"], "NOT_FOUND")

    def test_product_detail_get_success(self):
        dto = make_product_dto(5, "LookUp")
        service_mock = Mock()
        service_mock.get_product.return_value = dto
        with patch.object(ProductDetailView, "service", service_mock):
            request = self.factory.get("/api/products/5/")
            response = self.dispatch(request, ProductDetailView, product_id=5)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "LookUp")

    def test_product_detail_put_not_found(self):
        service_mock = Mock()
        service_mock.update_product.return_value = None
        payload = {
            "title": "Updated",
            "price": "20.00",
            "description": "Desc",
            "image": "img",
        }
        user = types.SimpleNamespace(
            id=2, is_authenticated=True, is_staff=True, is_superuser=False
        )
        with patch.object(ProductDetailView, "service", service_mock):
            request = self.factory.put("/api/products/1/", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, ProductDetailView, product_id=1)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"]["code"], "NOT_FOUND")

    def test_product_detail_delete_success(self):
        service_mock = Mock()
        service_mock.delete_product_with_auth.return_value = (True, None)
        user = types.SimpleNamespace(
            id=3, is_authenticated=True, is_staff=True, is_superuser=False
        )
        with patch.object(ProductDetailView, "service", service_mock):
            request = self.factory.delete("/api/products/2/")
            self.authenticate(request, user)
            response = self.dispatch(request, ProductDetailView, product_id=2)
        self.assertEqual(response.status_code, 204)

    def test_product_detail_delete_not_found(self):
        service_mock = Mock()
        service_mock.delete_product_with_auth.return_value = (
            False,
            ("NOT_FOUND", "Product not found", {"id": "8"}),
        )
        user = types.SimpleNamespace(
            id=9, is_authenticated=True, is_staff=True, is_superuser=False
        )
        with patch.object(ProductDetailView, "service", service_mock):
            request = self.factory.delete("/api/products/8/")
            self.authenticate(request, user)
            response = self.dispatch(request, ProductDetailView, product_id=8)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"]["code"], "NOT_FOUND")

    def test_product_detail_delete_forbidden_for_non_admin(self):
        service_mock = Mock()
        user = types.SimpleNamespace(
            id=13, is_authenticated=True, is_staff=False, is_superuser=False
        )
        with patch.object(ProductDetailView, "service", service_mock):
            request = self.factory.delete("/api/products/4/")
            self.authenticate(request, user)
            response = self.dispatch(request, ProductDetailView, product_id=4)
        self.assertEqual(response.status_code, 403)
        service_mock.delete_product_with_auth.assert_not_called()

    def test_product_detail_patch_returns_404_when_missing(self):
        service_mock = Mock()
        service_mock.update_product.return_value = None
        user = types.SimpleNamespace(
            id=4, is_authenticated=True, is_staff=True, is_superuser=False
        )
        with patch.object(ProductDetailView, "service", service_mock):
            request = self.factory.patch(
                "/api/products/3/", {"title": "New"}, format="json"
            )
            self.authenticate(request, user)
            response = self.dispatch(request, ProductDetailView, product_id=3)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"]["code"], "NOT_FOUND")

    def test_product_detail_put_success(self):
        dto = make_product_dto(6, "Updated")
        service_mock = Mock()
        service_mock.update_product.return_value = dto
        payload = {
            "title": "Updated",
            "price": "15.00",
            "description": "Desc",
            "image": "img",
        }
        user = types.SimpleNamespace(
            id=11, is_authenticated=True, is_staff=True, is_superuser=False
        )
        with patch.object(ProductDetailView, "service", service_mock):
            request = self.factory.put("/api/products/6/", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, ProductDetailView, product_id=6)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "Updated")

    def test_product_detail_put_forbidden_for_non_admin(self):
        service_mock = Mock()
        payload = {
            "title": "Updated",
            "price": "15.00",
            "description": "Desc",
            "image": "img",
        }
        user = types.SimpleNamespace(
            id=15, is_authenticated=True, is_staff=False, is_superuser=False
        )
        with patch.object(ProductDetailView, "service", service_mock):
            request = self.factory.put("/api/products/6/", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, ProductDetailView, product_id=6)
        self.assertEqual(response.status_code, 403)
        service_mock.update_product.assert_not_called()

    def test_product_detail_patch_success(self):
        updated = make_product_dto(7, "Patched")
        service_mock = Mock()
        service_mock.update_product.return_value = updated
        user = types.SimpleNamespace(
            id=12, is_authenticated=True, is_staff=True, is_superuser=False
        )
        with patch.object(ProductDetailView, "service", service_mock):
            request = self.factory.patch(
                "/api/products/7/", {"title": "Patched"}, format="json"
            )
            self.authenticate(request, user)
            response = self.dispatch(request, ProductDetailView, product_id=7)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "Patched")

    def test_category_list_get_and_post(self):
        categories = [make_category_dto(1, "A")]
        created = make_category_dto(2, "B")
        service_mock = Mock()
        service_mock.list_categories.return_value = categories
        service_mock.create_category_with_auth.return_value = (created, None)
        user = types.SimpleNamespace(
            id=20, is_authenticated=True, is_staff=True, is_superuser=False
        )
        with patch.object(CategoryListView, "service", service_mock):
            request_get = self.factory.get("/api/categories/")
            response_get = self.dispatch(request_get, CategoryListView)
        self.assertEqual(response_get.status_code, 200)
        self.assertEqual(response_get.data[0]["name"], "A")

        with patch.object(CategoryListView, "service", service_mock):
            request_post = self.factory.post(
                "/api/categories/", {"name": "B"}, format="json"
            )
            self.authenticate(request_post, user)
            response_post = self.dispatch(request_post, CategoryListView)
        self.assertEqual(response_post.status_code, 201)
        self.assertEqual(response_post.data["name"], "B")

    def test_category_post_forbidden_for_non_staff(self):
        service_mock = Mock()
        with patch.object(CategoryListView, "service", service_mock):
            request_post = self.factory.post(
                "/api/categories/", {"name": "B"}, format="json"
            )
            user = types.SimpleNamespace(
                id=21, is_authenticated=True, is_staff=False, is_superuser=False
            )
            self.authenticate(request_post, user)
            response_post = self.dispatch(request_post, CategoryListView)
        self.assertEqual(response_post.status_code, 403)
        service_mock.create_category_with_auth.assert_not_called()

    def test_category_detail_get_and_not_found(self):
        service_mock = Mock()
        service_mock.get_category.side_effect = [make_category_dto(3, "Found"), None]
        with patch.object(CategoryDetailView, "service", service_mock):
            request_get = self.factory.get("/api/categories/3/")
            response_get = self.dispatch(request_get, CategoryDetailView, category_id=3)
        self.assertEqual(response_get.status_code, 200)
        self.assertEqual(response_get.data["name"], "Found")

        with patch.object(CategoryDetailView, "service", service_mock):
            request_missing = self.factory.get("/api/categories/4/")
            response_missing = self.dispatch(
                request_missing, CategoryDetailView, category_id=4
            )
        self.assertEqual(response_missing.status_code, 404)
        self.assertEqual(response_missing.data["error"]["code"], "NOT_FOUND")

    def test_category_detail_put_patch_and_delete(self):
        service_mock = Mock()
        service_mock.update_category_with_auth.side_effect = [
            (make_category_dto(5, "Updated"), None),
            (None, ("NOT_FOUND", "Category not found", {"id": "5"})),
            (make_category_dto(5, "Patched"), None),
        ]
        service_mock.delete_category_with_auth.side_effect = [
            (False, ("NOT_FOUND", "Category not found", {"id": "5"})),
            (True, None),
        ]
        user = types.SimpleNamespace(
            id=30, is_authenticated=True, is_staff=True, is_superuser=False
        )

        with patch.object(CategoryDetailView, "service", service_mock):
            request_put = self.factory.put(
                "/api/categories/5/", {"name": "Updated"}, format="json"
            )
            self.authenticate(request_put, user)
            response_put = self.dispatch(request_put, CategoryDetailView, category_id=5)
        self.assertEqual(response_put.status_code, 200)
        self.assertEqual(response_put.data["name"], "Updated")

        with patch.object(CategoryDetailView, "service", service_mock):
            request_patch_missing = self.factory.patch(
                "/api/categories/5/", {"name": "Missing"}, format="json"
            )
            self.authenticate(request_patch_missing, user)
            response_patch_missing = self.dispatch(
                request_patch_missing, CategoryDetailView, category_id=5
            )
        self.assertEqual(response_patch_missing.status_code, 404)
        self.assertEqual(response_patch_missing.data["error"]["code"], "NOT_FOUND")

        with patch.object(CategoryDetailView, "service", service_mock):
            request_patch = self.factory.patch(
                "/api/categories/5/", {"name": "Patched"}, format="json"
            )
            self.authenticate(request_patch, user)
            response_patch = self.dispatch(
                request_patch, CategoryDetailView, category_id=5
            )
        self.assertEqual(response_patch.status_code, 200)
        self.assertEqual(response_patch.data["name"], "Patched")

        with patch.object(CategoryDetailView, "service", service_mock):
            request_delete_missing = self.factory.delete("/api/categories/5/")
            self.authenticate(request_delete_missing, user)
            response_delete_missing = self.dispatch(
                request_delete_missing, CategoryDetailView, category_id=5
            )
        self.assertEqual(response_delete_missing.status_code, 404)
        self.assertEqual(response_delete_missing.data["error"]["code"], "NOT_FOUND")

        with patch.object(CategoryDetailView, "service", service_mock):
            request_delete = self.factory.delete("/api/categories/5/")
            self.authenticate(request_delete, user)
            response_delete = self.dispatch(
                request_delete, CategoryDetailView, category_id=5
            )
        self.assertEqual(response_delete.status_code, 204)

    def test_category_detail_delete_forbidden_for_non_staff(self):
        service_mock = Mock()
        service_mock.delete_category_with_auth.return_value = (True, None)
        with patch.object(CategoryDetailView, "service", service_mock):
            request_delete = self.factory.delete("/api/categories/5/")
            user = types.SimpleNamespace(
                id=33, is_authenticated=True, is_staff=False, is_superuser=False
            )
            self.authenticate(request_delete, user)
            response = self.dispatch(request_delete, CategoryDetailView, category_id=5)
        self.assertEqual(response.status_code, 403)
        service_mock.delete_category_with_auth.assert_not_called()

    def test_category_detail_put_not_found(self):
        service_mock = Mock()
        service_mock.update_category_with_auth.return_value = (
            None,
            ("NOT_FOUND", "Category not found", {"id": "9"}),
        )
        user = types.SimpleNamespace(
            id=31, is_authenticated=True, is_staff=True, is_superuser=False
        )
        with patch.object(CategoryDetailView, "service", service_mock):
            request_put = self.factory.put(
                "/api/categories/9/", {"name": "Missing"}, format="json"
            )
            self.authenticate(request_put, user)
            response_put = self.dispatch(request_put, CategoryDetailView, category_id=9)
        self.assertEqual(response_put.status_code, 404)
        self.assertEqual(response_put.data["error"]["code"], "NOT_FOUND")

    def test_product_ratings_list_returns_data(self):
        service_mock = Mock()
        payload = {
            "productId": 1,
            "count": 1,
            "ratings": [
                {
                    "id": 10,
                    "firstName": "Admin",
                    "lastName": "User",
                    "value": 5,
                    "createdAt": "2025-01-01T00:00:00Z",
                    "updatedAt": "2025-01-01T00:00:00Z",
                }
            ],
        }
        service_mock.list_product_ratings.return_value = payload
        with patch.object(ProductRatingListView, "service", service_mock):
            request = self.factory.get("/api/products/1/ratings/")
            response = self.dispatch(request, ProductRatingListView, product_id=1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, payload)
        service_mock.list_product_ratings.assert_called_once_with(1)

    def test_product_ratings_list_handles_service_error(self):
        service_mock = Mock()
        service_mock.list_product_ratings.return_value = (
            "NOT_FOUND",
            "Product not found",
            {"id": 1},
        )
        with patch.object(ProductRatingListView, "service", service_mock):
            request = self.factory.get("/api/products/1/ratings/")
            response = self.dispatch(request, ProductRatingListView, product_id=1)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"]["code"], "NOT_FOUND")
        service_mock.list_product_ratings.assert_called_once_with(1)

    def test_product_ratings_list_allows_anonymous_access(self):
        service_mock = Mock()
        payload = {"productId": 2, "count": 0, "ratings": []}
        service_mock.list_product_ratings.return_value = payload
        with patch.object(ProductRatingListView, "service", service_mock):
            request = self.factory.get("/api/products/2/ratings/")
            response = self.dispatch(request, ProductRatingListView, product_id=2)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, payload)
        service_mock.list_product_ratings.assert_called_once_with(2)

    def test_product_rating_post_requires_authentication(self):
        service_mock = Mock()
        with patch.object(ProductRatingView, "service", service_mock):
            request = self.factory.post(
                "/api/products/1/rating/", {"value": 3}, format="json"
            )
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "UNAUTHORIZED")
        service_mock.set_user_rating.assert_not_called()

    def test_product_rating_post_handles_service_error(self):
        service_mock = Mock()
        service_mock.set_user_rating.return_value = ("NOT_FOUND", "missing", {"id": 1})
        user = types.SimpleNamespace(id=7, is_authenticated=True)
        with patch.object(ProductRatingView, "service", service_mock):
            request = self.factory.post(
                "/api/products/1/rating/", {"value": 4}, format="json"
            )
            self.authenticate(request, user)
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"]["code"], "NOT_FOUND")

    def test_product_rating_post_validates_value(self):
        service_mock = Mock()
        user = types.SimpleNamespace(id=5, is_authenticated=True)
        with patch.object(ProductRatingView, "service", service_mock):
            request = self.factory.post(
                "/api/products/1/rating/", {"value": "bad"}, format="json"
            )
            self.authenticate(request, user)
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        service_mock.set_user_rating.assert_not_called()

    def test_product_rating_post_rejects_staff(self):
        service_mock = Mock()
        staff_user = types.SimpleNamespace(
            id=2, is_authenticated=True, is_staff=True, is_superuser=False
        )
        with patch.object(ProductRatingView, "service", service_mock):
            request = self.factory.post(
                "/api/products/1/rating/", {"value": 4}, format="json"
            )
            self.authenticate(request, staff_user)
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "FORBIDDEN")
        service_mock.set_user_rating.assert_not_called()

    def test_product_rating_get_not_found(self):
        service_mock = Mock()
        service_mock.get_rating_summary.return_value = None
        user = types.SimpleNamespace(id=7, is_authenticated=True, is_staff=False, is_superuser=False)
        request = self.factory.get("/api/products/1/rating/")
        self.authenticate(request, user)
        with patch.object(ProductRatingView, "service", service_mock):
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"]["code"], "NOT_FOUND")

    def test_product_rating_get_requires_authentication(self):
        service_mock = Mock()
        request = self.factory.get("/api/products/1/rating/")
        with patch.object(ProductRatingView, "service", service_mock):
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "UNAUTHORIZED")
        service_mock.get_rating_summary.assert_not_called()

    def test_product_rating_post_staff_cannot_override_user(self):
        service_mock = Mock()
        admin = types.SimpleNamespace(
            id=1, is_authenticated=True, is_staff=True, is_superuser=False
        )
        with patch.object(ProductRatingView, "service", service_mock):
            request = self.factory.post(
                "/api/products/1/rating/?userId=77", {"value": 5}, format="json"
            )
            self.authenticate(request, admin)
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "FORBIDDEN")
        service_mock.set_user_rating.assert_not_called()

    def test_product_rating_post_non_privileged_override_forbidden(self):
        service_mock = Mock()
        service_mock.set_user_rating.return_value = {"rating": {"rate": 2, "count": 1}}
        user = types.SimpleNamespace(
            id=3, is_authenticated=True, is_staff=False, is_superuser=False
        )
        with patch.object(ProductRatingView, "service", service_mock):
            request = self.factory.post(
                "/api/products/1/rating/?userId=4", {"value": 2}, format="json"
            )
            self.authenticate(request, user)
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "FORBIDDEN")
        service_mock.set_user_rating.assert_not_called()

    def test_product_rating_post_invalid_query_user_id_rejected_for_staff(self):
        service_mock = Mock()
        admin = types.SimpleNamespace(
            id=1, is_authenticated=True, is_staff=True, is_superuser=False
        )
        with patch.object(ProductRatingView, "service", service_mock):
            request = self.factory.post(
                "/api/products/1/rating/?userId=bad", {"value": 4}, format="json"
            )
            self.authenticate(request, admin)
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "FORBIDDEN")
        service_mock.set_user_rating.assert_not_called()

    def test_product_rating_get_privileged_can_override_user(self):
        service_mock = Mock()
        service_mock.get_rating_summary.return_value = {
            "rating": {"rate": 4, "count": 1},
            "userRating": 4,
        }
        admin = types.SimpleNamespace(
            id=1, is_authenticated=True, is_staff=True, is_superuser=False
        )
        with patch.object(ProductRatingView, "service", service_mock):
            request = self.factory.get("/api/products/1/rating/?userId=77")
            self.authenticate(request, admin)
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 200)
        service_mock.get_rating_summary.assert_called_once_with(1, 77)

    def test_product_rating_get_non_privileged_override_forbidden(self):
        service_mock = Mock()
        service_mock.get_rating_summary.return_value = {
            "rating": {"rate": 4, "count": 1},
            "userRating": 4,
        }
        user = types.SimpleNamespace(
            id=3, is_authenticated=True, is_staff=False, is_superuser=False
        )
        with patch.object(ProductRatingView, "service", service_mock):
            request = self.factory.get("/api/products/1/rating/?userId=5")
            self.authenticate(request, user)
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "FORBIDDEN")
        service_mock.get_rating_summary.assert_not_called()

    def test_product_rating_get_invalid_query_user_id(self):
        service_mock = Mock()
        admin = types.SimpleNamespace(
            id=1, is_authenticated=True, is_staff=True, is_superuser=False
        )
        with patch.object(ProductRatingView, "service", service_mock):
            request = self.factory.get("/api/products/1/rating/?userId=bad")
            self.authenticate(request, admin)
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        service_mock.get_rating_summary.assert_not_called()

    def test_product_rating_delete_success_and_error(self):
        service_mock = Mock()
        service_mock.delete_rating.side_effect = [
            {"rating": {"rate": 0, "count": 0}},
            ("NOT_FOUND", "missing", {"ratingId": 5}),
        ]
        user = types.SimpleNamespace(
            id=77, is_authenticated=True, is_staff=False, is_superuser=False
        )
        request_success = self.factory.delete("/api/products/1/rating/?ratingId=5")
        self.authenticate(request_success, user)
        with patch.object(ProductRatingView, "service", service_mock):
            response_success = self.dispatch(
                request_success, ProductRatingView, product_id=1
            )
        self.assertEqual(response_success.status_code, 200)
        self.assertEqual(response_success.data["rating"]["count"], 0)
        service_mock.delete_rating.assert_called_with(
            1, 5, 77, False
        )

        request_error = self.factory.delete("/api/products/1/rating/?ratingId=5")
        self.authenticate(request_error, user)
        with patch.object(ProductRatingView, "service", service_mock):
            response_error = self.dispatch(
                request_error, ProductRatingView, product_id=1
            )
        self.assertEqual(response_error.status_code, 404)
        self.assertEqual(response_error.data["error"]["code"], "NOT_FOUND")

    def test_product_rating_delete_rejects_staff(self):
        service_mock = Mock()
        staff_user = types.SimpleNamespace(
            id=2, is_authenticated=True, is_staff=True, is_superuser=False
        )
        request = self.factory.delete(
            "/api/products/1/rating/?ratingId=5", format="json"
        )
        with patch.object(ProductRatingView, "service", service_mock):
            self.authenticate(request, staff_user)
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "FORBIDDEN")
        service_mock.delete_rating.assert_not_called()

    def test_product_rating_delete_requires_rating_id(self):
        service_mock = Mock()
        user = types.SimpleNamespace(
            id=55, is_authenticated=True, is_staff=False, is_superuser=False
        )
        request = self.factory.delete("/api/products/1/rating/")
        self.authenticate(request, user)
        with patch.object(ProductRatingView, "service", service_mock):
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        service_mock.delete_rating.assert_not_called()

    def test_product_rating_delete_invalid_rating_id(self):
        service_mock = Mock()
        user = types.SimpleNamespace(
            id=55, is_authenticated=True, is_staff=False, is_superuser=False
        )
        request = self.factory.delete("/api/products/1/rating/?ratingId=bad")
        self.authenticate(request, user)
        with patch.object(ProductRatingView, "service", service_mock):
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        service_mock.delete_rating.assert_not_called()

    def test_product_rating_delete_requires_user(self):
        service_mock = Mock()
        user = types.SimpleNamespace(id=None, is_authenticated=True)
        request = self.factory.delete("/api/products/1/rating/?ratingId=9")
        self.authenticate(request, user)
        with patch.object(ProductRatingView, "service", service_mock):
            response = self.dispatch(request, ProductRatingView, product_id=1)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "UNAUTHORIZED")
