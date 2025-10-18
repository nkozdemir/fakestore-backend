import types
import unittest
from unittest.mock import Mock, patch
from rest_framework.test import APIRequestFactory, force_authenticate
from apps.carts.views import CartListView, CartDetailView, CartByUserView
from apps.carts.services import CartAlreadyExistsError, CartNotAllowedError
from apps.api.validation import validate_request_context


def make_product_payload(product_id=1):
    return {
        "id": product_id,
        "title": f"Product {product_id}",
        "price": "10.00",
        "description": "Desc",
        "image": "img",
        "rate": "0",
        "count": 0,
        "categories": [],
    }


def make_cart_payload(cart_id=1, user_id=10):
    return {
        "id": cart_id,
        "user_id": user_id,
        "date": "2025-01-01",
        "items": [
            {
                "product": make_product_payload(),
                "quantity": 2,
            }
        ],
    }


class CartViewsUnitTests(unittest.TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user_flags = {}

        def filter_side_effect(**filters):
            user_id = filters.get("id")

            class ValuesWrapper:
                def __init__(self, info):
                    self._info = info

                def values(self, *args):
                    info = self._info

                    class FirstWrapper:
                        def __init__(self, info):
                            self._info = info

                        def first(self_inner):
                            return info

                    return FirstWrapper(info)

            if user_id is None:
                return ValuesWrapper(None)
            info = self.user_flags.get(
                user_id, {"id": user_id, "is_staff": False, "is_superuser": False}
            )
            return ValuesWrapper(info)

        self.user_patch = patch("apps.carts.views.User")
        self.mock_user_cls = self.user_patch.start()
        self.mock_user_cls.objects.filter.side_effect = filter_side_effect

    def dispatch(self, request, view_cls, **kwargs):
        pre_response = validate_request_context(request, view_cls, kwargs)
        if pre_response is not None:
            return pre_response
        view = view_cls.as_view()
        return view(request, **kwargs)

    def authenticate(self, request, user):
        request.user = user
        force_authenticate(request, user=user)

    def tearDown(self):
        self.user_patch.stop()

    @staticmethod
    def _user(user_id, *, staff=False, superuser=False):
        return types.SimpleNamespace(
            id=user_id,
            is_authenticated=True,
            is_staff=staff,
            is_superuser=superuser,
        )

    def test_cart_list_filters_by_user_param(self):
        carts = [make_cart_payload()]
        service_mock = Mock()
        service_mock.list_carts.return_value = carts
        with patch.object(CartListView, "service", service_mock):
            request = self.factory.get("/api/carts/", {"userId": 5})
            self.authenticate(request, self._user(1, staff=True))
            response = self.dispatch(request, CartListView)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, carts)
        service_mock.list_carts.assert_called_once_with(user_id=5)

    def test_cart_list_invalid_user_id_returns_validation_error(self):
        service_mock = Mock()
        with patch.object(CartListView, "service", service_mock):
            request = self.factory.get("/api/carts/", {"userId": "bad"})
            self.authenticate(request, self._user(1, staff=True))
            response = self.dispatch(request, CartListView)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        service_mock.list_carts.assert_not_called()

    def test_cart_list_post_requires_authenticated_user_id(self):
        service_mock = Mock()
        user = types.SimpleNamespace(
            id=None, is_authenticated=True, is_staff=False, is_superuser=False
        )
        with patch.object(CartListView, "service", service_mock):
            request = self.factory.post("/api/carts/", {"products": []}, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, CartListView)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "UNAUTHORIZED")
        service_mock.create_cart.assert_not_called()

    def test_cart_list_post_creates_cart_with_user_from_request(self):
        carts = make_cart_payload(cart_id=2, user_id=7)
        service_mock = Mock()
        service_mock.create_cart.return_value = carts
        service_mock.get_cart_for_user.return_value = None
        user = types.SimpleNamespace(
            id=7, is_authenticated=True, is_staff=False, is_superuser=False
        )
        payload = {
            "date": "2025-01-02",
            "products": [{"product_id": 1, "quantity": 2}],
        }
        with patch.object(CartListView, "service", service_mock):
            request = self.factory.post("/api/carts/", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, CartListView)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["id"], 2)
        args, _ = service_mock.create_cart.call_args
        self.assertEqual(args[0], 7)
        self.assertEqual(args[1]["products"][0]["product_id"], 1)

    def test_cart_list_post_admin_can_create_for_other_user(self):
        carts = make_cart_payload(cart_id=5, user_id=99)
        service_mock = Mock()
        service_mock.create_cart.return_value = carts
        service_mock.get_cart_for_user.return_value = None
        admin = types.SimpleNamespace(
            id=1, is_authenticated=True, is_staff=True, is_superuser=False
        )
        payload = {
            "date": "2025-02-01",
            "products": [{"product_id": 2, "quantity": 1}],
        }
        with patch.object(CartListView, "service", service_mock):
            request = self.factory.post("/api/carts/?userId=99", payload, format="json")
            self.authenticate(request, admin)
            response = self.dispatch(request, CartListView)
        self.assertEqual(response.status_code, 201)
        args, _ = service_mock.create_cart.call_args
        self.assertEqual(args[0], 99)
        self.assertNotIn("userId", args[1])

    def test_cart_list_post_non_admin_cannot_create_for_other_user(self):
        service_mock = Mock()
        service_mock.create_cart.return_value = make_cart_payload(cart_id=6, user_id=3)
        service_mock.get_cart_for_user.return_value = None
        user = types.SimpleNamespace(
            id=3, is_authenticated=True, is_staff=False, is_superuser=False
        )
        payload = {"products": [{"product_id": 4, "quantity": 1}]}
        with patch.object(CartListView, "service", service_mock):
            request = self.factory.post("/api/carts/?userId=9", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, CartListView)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "FORBIDDEN")
        service_mock.create_cart.assert_not_called()

    def test_cart_list_post_conflict_when_cart_exists(self):
        service_mock = Mock()
        service_mock.get_cart_for_user.return_value = make_cart_payload(
            cart_id=10, user_id=5
        )
        service_mock.create_cart.return_value = make_cart_payload(cart_id=11, user_id=5)
        user = types.SimpleNamespace(
            id=5, is_authenticated=True, is_staff=False, is_superuser=False
        )
        with patch.object(CartListView, "service", service_mock):
            request = self.factory.post("/api/carts/", {"products": []}, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, CartListView)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "CONFLICT")
        service_mock.create_cart.assert_not_called()

    def test_cart_list_post_for_staff_target_forbidden(self):
        service_mock = Mock()
        service_mock.get_cart_for_user.return_value = None
        service_mock.create_cart.return_value = make_cart_payload(cart_id=12, user_id=50)
        self.user_flags[50] = {"id": 50, "is_staff": True, "is_superuser": False}
        admin = types.SimpleNamespace(
            id=1, is_authenticated=True, is_staff=True, is_superuser=False
        )
        payload = {"products": []}
        with patch.object(CartListView, "service", service_mock):
            request = self.factory.post("/api/carts/?userId=50", payload, format="json")
            self.authenticate(request, admin)
            response = self.dispatch(request, CartListView)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "FORBIDDEN")
        service_mock.create_cart.assert_not_called()

    def test_cart_detail_get_not_found_returns_error(self):
        service_mock = Mock()
        service_mock.get_cart.return_value = None
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.get("/api/carts/1/")
            self.authenticate(request, self._user(1))
            response = self.dispatch(request, CartDetailView, cart_id=1)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"]["code"], "NOT_FOUND")

    def test_cart_detail_get_success(self):
        service_mock = Mock()
        cart = make_cart_payload(cart_id=11, user_id=4)
        service_mock.get_cart.return_value = cart
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.get("/api/carts/11/")
            self.authenticate(request, self._user(4))
            response = self.dispatch(request, CartDetailView, cart_id=11)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], 11)

    def test_cart_detail_put_requires_authenticated_user(self):
        service_mock = Mock()
        payload = {"items": []}
        user = types.SimpleNamespace(
            id=None, is_authenticated=True, is_staff=False, is_superuser=False
        )
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.put("/api/carts/1/", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, CartDetailView, cart_id=1)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "UNAUTHORIZED")

    def test_cart_detail_put_returns_not_found_when_service_returns_none(self):
        service_mock = Mock()
        service_mock.update_cart.return_value = None
        user = types.SimpleNamespace(
            id=9, is_authenticated=True, is_staff=False, is_superuser=False
        )
        payload = {"items": [], "date": "2025-01-01"}
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.put("/api/carts/1/", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, CartDetailView, cart_id=1)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"]["code"], "NOT_FOUND")

    def test_cart_detail_put_conflict_when_reassigning_to_user_with_cart(self):
        service_mock = Mock()
        service_mock.update_cart.side_effect = CartAlreadyExistsError("exists")
        user = types.SimpleNamespace(
            id=9, is_authenticated=True, is_staff=True, is_superuser=False
        )
        payload = {"user_id": 4}
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.put("/api/carts/2/", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, CartDetailView, cart_id=2)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "CONFLICT")

    def test_cart_detail_put_forbidden_reassign_by_non_admin(self):
        service_mock = Mock()
        user = types.SimpleNamespace(
            id=9, is_authenticated=True, is_staff=False, is_superuser=False
        )
        payload = {"items": [], "user_id": 10}
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.put("/api/carts/2/", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, CartDetailView, cart_id=2)
        self.assertEqual(response.status_code, 403)
        service_mock.update_cart.assert_not_called()

    def test_cart_detail_put_success(self):
        service_mock = Mock()
        updated = make_cart_payload(cart_id=2, user_id=9)
        service_mock.update_cart.return_value = updated
        user = types.SimpleNamespace(
            id=9, is_authenticated=True, is_staff=False, is_superuser=False
        )
        payload = {"items": [], "date": "2025-01-01"}
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.put("/api/carts/2/", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, CartDetailView, cart_id=2)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], 2)

    def test_cart_detail_put_admin_can_modify_other_cart(self):
        service_mock = Mock()
        updated = make_cart_payload(cart_id=2, user_id=9)
        service_mock.update_cart.return_value = updated
        admin = types.SimpleNamespace(
            id=1, is_authenticated=True, is_staff=True, is_superuser=False
        )
        payload = {"items": [], "date": "2025-01-01"}
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.put("/api/carts/2/", payload, format="json")
            self.authenticate(request, admin)
            response = self.dispatch(request, CartDetailView, cart_id=2)
        self.assertEqual(response.status_code, 200)
        args, kwargs = service_mock.update_cart.call_args
        self.assertEqual(args[0], 2)
        self.assertEqual(kwargs.get("user_id"), None)
        self.assertEqual(dict(args[1]), payload)

    def test_cart_detail_patch_returns_error_when_missing(self):
        service_mock = Mock()
        service_mock.patch_operations.return_value = None
        user = types.SimpleNamespace(
            id=4, is_authenticated=True, is_staff=False, is_superuser=False
        )
        payload = {"add": [{"product_id": 1, "quantity": 1}]}
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.patch("/api/carts/1/", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, CartDetailView, cart_id=1)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"]["code"], "NOT_FOUND")

    def test_cart_detail_patch_conflict_when_reassigning(self):
        service_mock = Mock()
        service_mock.patch_operations.side_effect = CartAlreadyExistsError("exists")
        admin = types.SimpleNamespace(
            id=1, is_authenticated=True, is_staff=True, is_superuser=False
        )
        payload = {"userId": 7}
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.patch("/api/carts/1/", payload, format="json")
            self.authenticate(request, admin)
            response = self.dispatch(request, CartDetailView, cart_id=1)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "CONFLICT")

    def test_cart_detail_patch_forbidden_when_reassigning_to_staff(self):
        service_mock = Mock()
        service_mock.patch_operations.side_effect = CartNotAllowedError(
            "Target user is not a customer"
        )
        admin = types.SimpleNamespace(
            id=1, is_authenticated=True, is_staff=True, is_superuser=False
        )
        payload = {"userId": 7}
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.patch("/api/carts/1/", payload, format="json")
            self.authenticate(request, admin)
            response = self.dispatch(request, CartDetailView, cart_id=1)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "FORBIDDEN")

    def test_cart_detail_patch_forbidden_reassign_by_non_admin(self):
        service_mock = Mock()
        user = types.SimpleNamespace(
            id=4, is_authenticated=True, is_staff=False, is_superuser=False
        )
        payload = {"userId": 20}
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.patch("/api/carts/1/", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, CartDetailView, cart_id=1)
        self.assertEqual(response.status_code, 403)
        service_mock.patch_operations.assert_not_called()

    def test_cart_detail_patch_success(self):
        service_mock = Mock()
        patched = make_cart_payload(cart_id=1, user_id=4)
        service_mock.patch_operations.return_value = patched
        user = types.SimpleNamespace(
            id=4, is_authenticated=True, is_staff=False, is_superuser=False
        )
        payload = {"add": [{"product_id": 1, "quantity": 1}]}
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.patch("/api/carts/1/", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, CartDetailView, cart_id=1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], 1)

    def test_cart_detail_patch_admin_on_other_cart(self):
        service_mock = Mock()
        patched = make_cart_payload(cart_id=1, user_id=10)
        service_mock.patch_operations.return_value = patched
        admin = types.SimpleNamespace(
            id=1, is_authenticated=True, is_staff=True, is_superuser=False
        )
        payload = {"add": [{"product_id": 1, "quantity": 1}]}
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.patch("/api/carts/1/", payload, format="json")
            self.authenticate(request, admin)
            response = self.dispatch(request, CartDetailView, cart_id=1)
        self.assertEqual(response.status_code, 200)
        args, kwargs = service_mock.patch_operations.call_args
        self.assertEqual(args[0], 1)
        self.assertEqual(kwargs.get("user_id"), None)
        self.assertEqual(args[1], payload)

    def test_cart_detail_patch_requires_authentication(self):
        service_mock = Mock()
        payload = {"add": [{"product_id": 1, "quantity": 1}]}
        user = types.SimpleNamespace(
            id=None, is_authenticated=True, is_staff=False, is_superuser=False
        )
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.patch("/api/carts/1/", payload, format="json")
            self.authenticate(request, user)
            response = self.dispatch(request, CartDetailView, cart_id=1)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "UNAUTHORIZED")

    def test_cart_detail_delete_success(self):
        service_mock = Mock()
        service_mock.delete_cart.return_value = True
        user = types.SimpleNamespace(
            id=3, is_authenticated=True, is_staff=False, is_superuser=False
        )
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.delete("/api/carts/1/")
            self.authenticate(request, user)
            response = self.dispatch(request, CartDetailView, cart_id=1)
        self.assertEqual(response.status_code, 204)
        service_mock.delete_cart.assert_called_once_with(1, user_id=3)

    def test_cart_detail_delete_not_found(self):
        service_mock = Mock()
        service_mock.delete_cart.return_value = False
        user = types.SimpleNamespace(
            id=3, is_authenticated=True, is_staff=False, is_superuser=False
        )
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.delete("/api/carts/1/")
            self.authenticate(request, user)
            response = self.dispatch(request, CartDetailView, cart_id=1)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"]["code"], "NOT_FOUND")

    def test_cart_detail_delete_admin_other_cart(self):
        service_mock = Mock()
        service_mock.delete_cart.return_value = True
        admin = types.SimpleNamespace(
            id=1, is_authenticated=True, is_staff=True, is_superuser=False
        )
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.delete("/api/carts/9/")
            self.authenticate(request, admin)
            response = self.dispatch(request, CartDetailView, cart_id=9)
        self.assertEqual(response.status_code, 204)
        service_mock.delete_cart.assert_called_once_with(9, user_id=None)

    def test_cart_detail_delete_requires_authentication(self):
        service_mock = Mock()
        user = types.SimpleNamespace(
            id=None, is_authenticated=True, is_staff=False, is_superuser=False
        )
        with patch.object(CartDetailView, "service", service_mock):
            request = self.factory.delete("/api/carts/1/")
            self.authenticate(request, user)
            response = self.dispatch(request, CartDetailView, cart_id=1)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "UNAUTHORIZED")

    def test_cart_by_user_view_returns_data(self):
        carts = [make_cart_payload(cart_id=5, user_id=12)]
        service_mock = Mock()
        service_mock.list_carts.return_value = carts
        with patch.object(CartByUserView, "service", service_mock):
            request = self.factory.get("/api/users/12/carts/")
            self.authenticate(request, self._user(12))
            response = self.dispatch(request, CartByUserView, user_id=12)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, carts)
        service_mock.list_carts.assert_called_once_with(user_id=12)
