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
from apps.users.models import User

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
        is_privileged = bool(getattr(request, "is_privileged_user", False))
        actor_id = getattr(request, "validated_user_id", None)
        # Support both userId (camelCase) and user_id (snake_case)
        user_id_param = request.query_params.get("userId") or request.query_params.get("user_id")
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
        if user_id is not None:
            # Privileged callers can fetch cart lists for any user.
            if is_privileged:
                self.log.debug("Listing carts via API", user_id=user_id)
                data = self.service.list_carts(user_id=user_id)
                serializer = CartReadSerializer(data, many=True)
                return Response(serializer.data)
            # Non-privileged callers may only fetch their own cart.
            if actor_id is None:
                self.log.warning("Unauthorized cart lookup", requested_user_id=user_id_param)
                return error_response("UNAUTHORIZED", "Authentication required")
            if int(actor_id) != user_id:
                self.log.warning(
                    "Cart lookup forbidden for other user",
                    actor_id=actor_id,
                    requested_user_id=user_id,
                )
                return error_response(
                    "FORBIDDEN",
                    "You do not have permission to view this user's carts",
                    {"userId": user_id_param},
                )
            try:
                dto, _created = self.service.get_or_create_cart(user_id)
            except CartNotAllowedError as exc:
                self.log.warning(
                    "Cart access not allowed for user",
                    actor_id=actor_id,
                    target_user_id=user_id,
                    error=str(exc),
                )
                code = "NOT_FOUND" if "does not exist" in str(exc) else "FORBIDDEN"
                message = (
                    "Target user not found"
                    if code == "NOT_FOUND"
                    else "Staff and admin accounts cannot own carts"
                )
                return error_response(code, message, {"userId": user_id_param})
            except CartAlreadyExistsError:
                dto = self.service.get_cart_for_user(user_id)
            payload = [dto] if dto else []
            serializer = CartReadSerializer(payload, many=True)
            self.log.debug(
                "Returning cart for user via query lookup",
                actor_id=actor_id,
                user_id=user_id,
                has_cart=bool(dto),
            )
            return Response(serializer.data)

        if not is_privileged:
            self.log.warning(
                "Cart list forbidden",
                actor_id=actor_id,
            )
            return error_response(
                "FORBIDDEN", "You do not have permission to list carts"
            )
        self.log.debug("Listing carts via API without filter")
        data = self.service.list_carts()
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
        user_id = getattr(request, "validated_user_id", None)
        if user_id is None:
            self.log.warning("Unauthorized cart creation attempt")
            return error_response("UNAUTHORIZED", "Authentication required")
        is_privileged = bool(getattr(request, "is_privileged_user", False))
        payload = dict(serializer.validated_data)
        target_user_id = user_id
        raw_user_id = request.query_params.get("userId") or request.query_params.get(
            "user_id"
        )
        if raw_user_id is not None:
            try:
                desired_user_id = int(raw_user_id)
            except (TypeError, ValueError):
                self.log.warning(
                    "Invalid userId query parameter provided for cart creation",
                    raw_value=raw_user_id,
                )
                return error_response(
                    "VALIDATION_ERROR",
                    "userId must be an integer",
                    {"userId": raw_user_id},
                )
            if is_privileged:
                target_user_id = desired_user_id
            elif desired_user_id != user_id:
                self.log.warning(
                    "Cart creation forbidden for non-privileged override",
                    actor_id=user_id,
                    desired_user_id=desired_user_id,
                )
                return error_response(
                    "FORBIDDEN",
                    "You do not have permission to create carts for other users",
                    {"userId": str(desired_user_id)},
                )
        target_user = (
            User.objects.filter(id=target_user_id)
            .values("id", "is_staff", "is_superuser")
            .first()
        )
        if not target_user:
            self.log.warning(
                "Cart creation failed: user not found", target_user_id=target_user_id
            )
            return error_response(
                "NOT_FOUND", "Target user not found", {"userId": str(target_user_id)}
            )
        if target_user["is_staff"] or target_user["is_superuser"]:
            self.log.warning(
                "Cart creation forbidden for staff/admin",
                actor_id=user_id,
                target_user_id=target_user_id,
            )
            return error_response(
                "FORBIDDEN",
                "Staff and admin accounts cannot own carts",
                {"userId": str(target_user_id)},
            )
        try:
            dto, created = self.service.get_or_create_cart(
                int(target_user_id), payload
            )
        except CartNotAllowedError as exc:
            self.log.warning(
                "Cart creation not allowed",
                actor_id=user_id,
                target_user_id=target_user_id,
                error=str(exc),
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
                {"userId": str(target_user_id)},
            )
        except CartAlreadyExistsError:
            # Should be rare since get_or_create guards, but guard against unexpected cases.
            self.log.warning(
                "Cart creation conflict (race)",
                actor_id=user_id,
                target_user_id=target_user_id,
            )
            return error_response(
                "CONFLICT",
                "User already has a cart",
                {"userId": str(target_user_id)},
            )
        cart_id = getattr(dto, "id", None)
        if cart_id is None and isinstance(dto, dict):
            cart_id = dto.get("id")
        self.log.info(
            "Cart ensured via API",
            cart_id=cart_id,
            user_id=target_user_id,
            actor_id=user_id,
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
            403: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
            409: OpenApiResponse(response=ErrorResponseSerializer),
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
            403: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
            409: OpenApiResponse(response=ErrorResponseSerializer),
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
