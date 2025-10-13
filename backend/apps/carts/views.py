from typing import Optional

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .container import build_cart_service
from .serializers import (
    CartReadSerializer,
    CartWriteSerializer,
    CartCreateSerializer,
    CartItemWriteSerializer,
)
from apps.api.utils import error_response
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from apps.api.schemas import ErrorResponseSerializer
from apps.common import get_logger

logger = get_logger(__name__).bind(component="carts", layer="view")


class CartPatchSerializer(serializers.Serializer):
    add = CartItemWriteSerializer(many=True, required=False)
    update = CartItemWriteSerializer(many=True, required=False)
    remove = serializers.ListField(child=serializers.IntegerField(), required=False)
    date = serializers.CharField(required=False)
    userId = serializers.IntegerField(required=False)


@extend_schema(tags=["Carts"])
class CartListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = build_cart_service()
    log = logger.bind(view="CartListView")

    @extend_schema(
        summary="List carts",
        parameters=[
            OpenApiParameter(
                name="userId",
                description="Filter by user ID (preferred)",
                required=False,
                type=int,
            ),
        ],
        responses={200: CartReadSerializer(many=True)},
    )
    def get(self, request):
        is_privileged = bool(getattr(request, "is_privileged_user", False))
        actor_id = getattr(request, "validated_user_id", None)
        if not is_privileged:
            self.log.warning(
                "Cart list forbidden",
                actor_id=actor_id,
            )
            return error_response(
                "FORBIDDEN", "You do not have permission to list carts"
            )
        # Support both userId (camelCase) and user_id (snake_case)
        user_id_param = request.query_params.get("userId") or request.query_params.get(
            "user_id"
        )
        user_id: Optional[int] = None
        if user_id_param is not None:
            try:
                user_id = int(user_id_param)
            except (TypeError, ValueError):
                self.log.warning(
                    "Invalid userId query parameter",
                    user_id=user_id_param,
                    path=request.path,
                )
                return error_response(
                    "VALIDATION_ERROR",
                    "userId must be an integer",
                    {"userId": user_id_param},
                )
        self.log.debug("Listing carts via API", user_id=user_id)
        data = (
            self.service.list_carts(user_id=user_id)
            if user_id is not None
            else self.service.list_carts()
        )
        serializer = CartReadSerializer(data, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create cart",
        description=(
            "Creates a new cart for the authenticated user. The user is derived from the JWT in the "
            "Authorization header. Regular users should not include userId in the request body; staff or "
            "superusers may specify userId to create carts for other users. Optionally include initial "
            "products to seed line items."
        ),
        request=CartCreateSerializer,
        responses={
            201: CartReadSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
            401: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def post(self, request):
        serializer = CartCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = getattr(request, "validated_user_id", None)
        if user_id is None:
            self.log.warning("Unauthorized cart creation attempt")
            return error_response("UNAUTHORIZED", "Authentication required")
        is_privileged = bool(getattr(request, "is_privileged_user", False))
        payload = dict(serializer.validated_data)
        target_user_id = user_id
        if is_privileged and "userId" in serializer.validated_data:
            raw_user_id = serializer.validated_data.get("userId")
            try:
                target_user_id = int(raw_user_id)
            except (TypeError, ValueError):
                self.log.warning(
                    "Invalid userId provided for cart creation",
                    raw_value=raw_user_id,
                )
                return error_response(
                    "VALIDATION_ERROR",
                    "userId must be an integer",
                    {"userId": raw_user_id},
                )
        payload.pop("userId", None)
        self.log.info(
            "Creating cart via API",
            user_id=target_user_id,
            actor_id=user_id,
            privileged=is_privileged,
        )
        dto = self.service.create_cart(int(target_user_id), payload)
        cart_id = getattr(dto, "id", None)
        if cart_id is None and isinstance(dto, dict):
            cart_id = dto.get("id")
        self.log.info(
            "Cart created via API",
            cart_id=cart_id,
            user_id=target_user_id,
            actor_id=user_id,
        )
        return Response(CartReadSerializer(dto).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Carts"])
class CartDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = build_cart_service()
    log = logger.bind(view="CartDetailView")

    @extend_schema(
        summary="Get cart",
        parameters=[OpenApiParameter("cart_id", int, OpenApiParameter.PATH)],
        responses={
            200: CartReadSerializer,
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def get(self, request, cart_id: int):
        actor_id = getattr(request, "validated_user_id", None)
        is_privileged = bool(getattr(request, "is_privileged_user", False))
        if actor_id is None and not is_privileged:
            self.log.warning("Unauthorized cart detail access", cart_id=cart_id)
            return error_response("UNAUTHORIZED", "Authentication required")
        self.log.debug("Fetching cart detail", cart_id=cart_id)
        dto = self.service.get_cart(cart_id)
        if not dto:
            self.log.info("Cart not found", cart_id=cart_id)
            return error_response("NOT_FOUND", "Cart not found", {"id": str(cart_id)})
        owner_id = getattr(dto, "user_id", None)
        if owner_id is None and isinstance(dto, dict):
            owner_id = dto.get("user_id")
        if not is_privileged and owner_id != actor_id:
            self.log.warning(
                "Cart detail forbidden",
                cart_id=cart_id,
                actor_id=actor_id,
                owner_id=owner_id,
            )
            return error_response(
                "FORBIDDEN", "You do not have permission to view this cart"
            )
        serializer = CartReadSerializer(dto)
        return Response(serializer.data)

    @extend_schema(
        summary="Replace cart",
        description=(
            "Replaces the cart. Requires authentication and only the owner can update their cart unless they are "
            "staff or superuser. If unauthenticated, returns 401. If the cart does not exist or the actor lacks "
            "permission, returns 404 or 403 respectively."
        ),
        request=CartWriteSerializer,
        responses={
            200: CartReadSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
            401: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def put(self, request, cart_id: int):
        user_id = getattr(request, "validated_user_id", None)
        if user_id is None:
            self.log.warning("Unauthorized cart replace attempt", cart_id=cart_id)
            return error_response("UNAUTHORIZED", "Authentication required")
        is_privileged = bool(getattr(request, "is_privileged_user", False))
        actor_id = int(user_id)
        serializer = CartWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not is_privileged:
            desired_user_id = serializer.validated_data.get("user_id")
            if desired_user_id is not None and int(desired_user_id) != actor_id:
                self.log.warning(
                    "Forbidden cart reassignment attempt",
                    cart_id=cart_id,
                    actor_id=actor_id,
                    desired_user_id=desired_user_id,
                )
                return error_response(
                    "FORBIDDEN", "You do not have permission to reassign this cart"
                )
        scope_user_id: Optional[int] = None if is_privileged else actor_id
        self.log.info(
            "Replacing cart",
            cart_id=cart_id,
            actor_id=actor_id,
            scoped_user_id=scope_user_id,
        )
        dto = self.service.update_cart(
            cart_id, serializer.validated_data, user_id=scope_user_id
        )
        if not dto:
            self.log.warning(
                "Cart replace failed: not found",
                cart_id=cart_id,
                actor_id=actor_id,
                scoped_user_id=scope_user_id,
            )
            return error_response("NOT_FOUND", "Cart not found", {"id": str(cart_id)})
        return Response(CartReadSerializer(dto).data)

    @extend_schema(
        summary="Patch cart items",
        description=(
            "Applies add/update/remove item operations. Requires authentication and only the owner can patch their cart "
            "unless they are staff or superuser. If unauthenticated, returns 401. If the cart does not exist or the actor "
            "lacks permission, returns 404 or 403 respectively."
        ),
        request=CartPatchSerializer,
        responses={
            200: CartReadSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
            401: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def patch(self, request, cart_id: int):
        user_id = getattr(request, "validated_user_id", None)
        if user_id is None:
            self.log.warning("Unauthorized cart patch attempt", cart_id=cart_id)
            return error_response("UNAUTHORIZED", "Authentication required")
        is_privileged = bool(getattr(request, "is_privileged_user", False))
        actor_id = int(user_id)
        # Interpret patch operations for cart items
        ops_serializer = CartPatchSerializer(data=request.data)
        ops_serializer.is_valid(raise_exception=True)
        if not is_privileged:
            desired_user_id = ops_serializer.validated_data.get("userId")
            if desired_user_id is not None and int(desired_user_id) != actor_id:
                self.log.warning(
                    "Forbidden cart reassignment patch",
                    cart_id=cart_id,
                    actor_id=actor_id,
                    desired_user_id=desired_user_id,
                )
                return error_response(
                    "FORBIDDEN", "You do not have permission to reassign this cart"
                )
        scope_user_id: Optional[int] = None if is_privileged else actor_id
        self.log.info(
            "Applying cart patch",
            cart_id=cart_id,
            actor_id=actor_id,
            scoped_user_id=scope_user_id,
        )
        dto = self.service.patch_operations(
            cart_id, ops_serializer.validated_data, user_id=scope_user_id
        )
        if not dto:
            self.log.warning(
                "Cart patch failed: not found",
                cart_id=cart_id,
                actor_id=actor_id,
                scoped_user_id=scope_user_id,
            )
            return error_response("NOT_FOUND", "Cart not found", {"id": str(cart_id)})
        return Response(CartReadSerializer(dto).data)

    @extend_schema(
        summary="Delete cart",
        description=(
            "Deletes a cart. Requires authentication; only the owner can delete their cart unless they are staff or "
            "superuser. If unauthenticated, returns 401. If the cart does not exist or the actor lacks permission, "
            "returns 404 or 403 respectively."
        ),
        responses={
            204: None,
            401: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def delete(self, request, cart_id: int):
        user_id = getattr(request, "validated_user_id", None)
        if user_id is None:
            self.log.warning("Unauthorized cart delete attempt", cart_id=cart_id)
            return error_response("UNAUTHORIZED", "Authentication required")
        is_privileged = bool(getattr(request, "is_privileged_user", False))
        actor_id = int(user_id)
        scope_user_id: Optional[int] = None if is_privileged else actor_id
        self.log.info(
            "Deleting cart via API",
            cart_id=cart_id,
            actor_id=actor_id,
            scoped_user_id=scope_user_id,
        )
        deleted = self.service.delete_cart(cart_id, user_id=scope_user_id)
        if not deleted:
            self.log.warning(
                "Cart delete failed: not found",
                cart_id=cart_id,
                actor_id=actor_id,
                scoped_user_id=scope_user_id,
            )
            return error_response("NOT_FOUND", "Cart not found", {"id": str(cart_id)})
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Carts"])
class CartByUserView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = build_cart_service()
    log = logger.bind(view="CartByUserView")

    @extend_schema(
        summary="List carts by user",
        parameters=[OpenApiParameter("user_id", int, OpenApiParameter.PATH)],
        responses={200: CartReadSerializer(many=True)},
    )
    def get(self, request, user_id: int):
        actor_id = getattr(request, "validated_user_id", None)
        is_privileged = bool(getattr(request, "is_privileged_user", False))
        if actor_id is None and not is_privileged:
            self.log.warning(
                "Unauthorized cart-by-user access attempt",
                target_user_id=user_id,
            )
            return error_response("UNAUTHORIZED", "Authentication required")
        if not is_privileged and actor_id != int(user_id):
            self.log.warning(
                "Cart-by-user forbidden",
                actor_id=actor_id,
                target_user_id=user_id,
            )
            return error_response(
                "FORBIDDEN",
                "You do not have permission to view this user's carts",
            )
        self.log.debug("Listing carts for user", user_id=user_id)
        data = self.service.list_carts(user_id=user_id)
        serializer = CartReadSerializer(data, many=True)
        return Response(serializer.data)
