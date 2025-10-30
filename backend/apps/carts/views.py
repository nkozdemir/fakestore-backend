from typing import Optional

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .container import build_cart_service
from .services import CartAlreadyExistsError, CartNotAllowedError
from .serializers import (
    CartReadSerializer,
    CartWriteSerializer,
    CartCreateSerializer,
    CartItemWriteSerializer,
)
from apps.api.utils import error_response
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
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


class CartListView(APIView):
    permission_classes = [IsAuthenticated]
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
        actor_id = getattr(request, "validated_user_id", None)
        is_privileged = bool(getattr(request, "cart_is_privileged", False))
        mode = getattr(request, "cart_list_mode", None)
        target_user_id = getattr(request, "cart_list_target_user_id", None)
        data, error = self.service.list_carts_with_auth(
            actor_id=actor_id,
            is_privileged=is_privileged,
            mode=mode,
            target_user_id=target_user_id,
        )
        if error:
            code, message, details = error
            return error_response(code, message, details)
        serializer = CartReadSerializer(data, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create cart",
        description=(
            "Creates a new cart for the authenticated user. The user is derived from the JWT in the "
            "Authorization header. Staff or superusers may pass userId as a query parameter to create carts "
            "for other users. Optionally include initial products to seed line items."
        ),
        parameters=[
            OpenApiParameter(
                name="userId",
                description="Override the target user when the caller is privileged",
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            )
        ],
        request=CartCreateSerializer,
        responses={
            201: CartReadSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
            401: OpenApiResponse(response=ErrorResponseSerializer),
            403: OpenApiResponse(response=ErrorResponseSerializer),
            409: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def post(self, request):
        serializer = CartCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actor_id = getattr(request, "validated_user_id", None)
        is_privileged = bool(getattr(request, "cart_is_privileged", False))
        target_user_id = getattr(request, "cart_target_user_id", actor_id)
        payload = dict(serializer.validated_data)
        dto, created, error = self.service.create_cart_with_auth(
            actor_id=actor_id,
            target_user_id=target_user_id,
            payload=payload,
            is_privileged=is_privileged,
        )
        if error:
            code, message, details = error
            return error_response(code, message, details)
        cart_id = getattr(dto, "id", None)
        if cart_id is None and isinstance(dto, dict):
            cart_id = dto.get("id")
        self.log.info(
            "Cart ensured via API",
            cart_id=cart_id,
            user_id=target_user_id,
            actor_id=actor_id,
            created=created,
            privileged=is_privileged,
        )
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(CartReadSerializer(dto).data, status=response_status)
class CartDetailView(APIView):
    permission_classes = [IsAuthenticated]
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
        self.log.debug(
            "Fetching cart detail",
            cart_id=cart_id,
            actor_id=actor_id,
            privileged=is_privileged,
        )
        dto, error = self.service.get_cart_with_access(cart_id, actor_id, is_privileged)
        if error:
            code, message, details = error
            return error_response(code, message, details)
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
            403: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
            409: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def put(self, request, cart_id: int):
        actor_id = getattr(request, "validated_user_id", None)
        is_privileged = bool(getattr(request, "is_privileged_user", False))
        serializer = CartWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        desired_user_id = serializer.validated_data.get("user_id")
        dto, error = self.service.authorize_cart_mutation(
            cart_id,
            actor_id=None if actor_id is None else int(actor_id),
            is_privileged=is_privileged,
            desired_user_id=desired_user_id,
        )
        if error:
            code, message, details = error
            return error_response(code, message, details)
        resolved_actor = None if actor_id is None else int(actor_id)
        scope_user_id: Optional[int] = None if is_privileged else resolved_actor
        self.log.info(
            "Replacing cart",
            cart_id=cart_id,
            actor_id=resolved_actor,
            scoped_user_id=scope_user_id,
        )
        try:
            dto = self.service.update_cart(
                cart_id, serializer.validated_data, user_id=scope_user_id
            )
        except CartAlreadyExistsError:
            conflict_user = serializer.validated_data.get("user_id")
            self.log.warning(
                "Cart replace conflict",
                cart_id=cart_id,
                actor_id=actor_id,
                target_user=conflict_user,
            )
            return error_response(
                "CONFLICT",
                "Target user already has a cart",
                {"userId": str(conflict_user) if conflict_user is not None else None},
            )
        except CartNotAllowedError as exc:
            conflict_user = serializer.validated_data.get("user_id")
            self.log.warning(
                "Cart replace forbidden for staff/admin",
                cart_id=cart_id,
                actor_id=actor_id,
                target_user=conflict_user,
            )
            code = "NOT_FOUND" if "does not exist" in str(exc) else "FORBIDDEN"
            message = (
                "Target user not found"
                if code == "NOT_FOUND"
                else "Staff and admin accounts cannot own carts"
            )
            return error_response(
                code,
                message,
                {"userId": str(conflict_user) if conflict_user is not None else None},
            )
        if not dto:
            self.log.warning(
                "Cart replace failed: not found",
                cart_id=cart_id,
                actor_id=resolved_actor,
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
            403: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
            409: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def patch(self, request, cart_id: int):
        actor_id = getattr(request, "validated_user_id", None)
        is_privileged = bool(getattr(request, "is_privileged_user", False))
        # Interpret patch operations for cart items
        ops_serializer = CartPatchSerializer(data=request.data)
        ops_serializer.is_valid(raise_exception=True)
        desired_user_id = ops_serializer.validated_data.get("userId")
        dto, error = self.service.authorize_cart_mutation(
            cart_id,
            actor_id=None if actor_id is None else int(actor_id),
            is_privileged=is_privileged,
            desired_user_id=desired_user_id,
        )
        if error:
            code, message, details = error
            return error_response(code, message, details)
        resolved_actor = None if actor_id is None else int(actor_id)
        scope_user_id: Optional[int] = None if is_privileged else resolved_actor
        self.log.info(
            "Applying cart patch",
            cart_id=cart_id,
            actor_id=resolved_actor,
            scoped_user_id=scope_user_id,
        )
        try:
            dto = self.service.patch_operations(
                cart_id, ops_serializer.validated_data, user_id=scope_user_id
            )
        except CartAlreadyExistsError:
            conflict_user = ops_serializer.validated_data.get("userId")
            self.log.warning(
                "Cart patch conflict",
                cart_id=cart_id,
                actor_id=actor_id,
                target_user=conflict_user,
            )
            return error_response(
                "CONFLICT",
                "Target user already has a cart",
                {"userId": str(conflict_user) if conflict_user is not None else None},
            )
        except CartNotAllowedError as exc:
            conflict_user = ops_serializer.validated_data.get("userId")
            self.log.warning(
                "Cart patch forbidden for staff/admin",
                cart_id=cart_id,
                actor_id=actor_id,
                target_user=conflict_user,
            )
            code = "NOT_FOUND" if "does not exist" in str(exc) else "FORBIDDEN"
            message = (
                "Target user not found"
                if code == "NOT_FOUND"
                else "Staff and admin accounts cannot own carts"
            )
            return error_response(
                code,
                message,
                {"userId": str(conflict_user) if conflict_user is not None else None},
            )
        if not dto:
            self.log.warning(
                "Cart patch failed: not found",
                cart_id=cart_id,
                actor_id=resolved_actor,
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
        actor_id = getattr(request, "validated_user_id", None)
        is_privileged = bool(getattr(request, "is_privileged_user", False))
        dto, error = self.service.authorize_cart_mutation(
            cart_id,
            actor_id=None if actor_id is None else int(actor_id),
            is_privileged=is_privileged,
        )
        if error:
            code, message, details = error
            return error_response(code, message, details)
        resolved_actor = None if actor_id is None else int(actor_id)
        scope_user_id: Optional[int] = None if is_privileged else resolved_actor
        self.log.info(
            "Deleting cart via API",
            cart_id=cart_id,
            actor_id=resolved_actor,
            scoped_user_id=scope_user_id,
        )
        deleted = self.service.delete_cart(cart_id, user_id=scope_user_id)
        if not deleted:
            self.log.warning(
                "Cart delete failed: not found",
                cart_id=cart_id,
                actor_id=resolved_actor,
                scoped_user_id=scope_user_id,
            )
            return error_response("NOT_FOUND", "Cart not found", {"id": str(cart_id)})
        return Response(status=status.HTTP_204_NO_CONTENT)
