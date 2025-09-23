from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import CartService
from .serializers import CartReadSerializer, CartWriteSerializer, CartCreateSerializer
from apps.api.utils import error_response
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from apps.api.schemas import ErrorResponseSerializer

class CartPatchSerializer(serializers.Serializer):
    add = serializers.ListField(child=serializers.DictField(), required=False)
    update = serializers.ListField(child=serializers.DictField(), required=False)
    remove = serializers.ListField(child=serializers.IntegerField(), required=False)
    date = serializers.CharField(required=False)
    userId = serializers.IntegerField(required=False)

@extend_schema(tags=["Carts"])
class CartListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = CartService()
    @extend_schema(
        summary="List carts",
        parameters=[
            OpenApiParameter(name="userId", description="Filter by user ID (preferred)", required=False, type=int),
        ],
        responses={200: CartReadSerializer(many=True)},
    )
    def get(self, request):
        # Support both userId (camelCase) and user_id (snake_case)
        user_id_param = request.query_params.get('userId') or request.query_params.get('user_id')
        data = self.service.list_carts(user_id=int(user_id_param)) if user_id_param else self.service.list_carts()
        serializer = CartReadSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=False)
        return Response(serializer.data)
    @extend_schema(
        summary="Create cart",
        description=(
            "Creates a new cart for the authenticated user. The user is derived from the JWT in the "
            "Authorization header; do not include userId in the request body. Optionally include initial "
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
        # Infer user from JWT-authenticated request and inject into payload
        user_id = getattr(request.user, 'id', None)
        if not user_id:
            return error_response('UNAUTHORIZED', 'Authentication required')
        payload = dict(serializer.validated_data)
        payload['userId'] = int(user_id)
        dto = self.service.create_cart(payload)
        return Response(CartReadSerializer(dto).data, status=status.HTTP_201_CREATED)

@extend_schema(tags=["Carts"])
class CartDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = CartService()
    @extend_schema(
        summary="Get cart",
        parameters=[OpenApiParameter("cart_id", int, OpenApiParameter.PATH)],
        responses={200: CartReadSerializer, 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def get(self, request, cart_id: int):
        dto = self.service.get_cart(cart_id)
        if not dto:
            return error_response('NOT_FOUND', 'Cart not found', {'id': str(cart_id)})
        serializer = CartReadSerializer(dto)
        return Response(serializer.data)
    @extend_schema(
        summary="Replace cart",
        description=(
            "Replaces the cart. Requires authentication and only the owner can update their cart. "
            "If unauthenticated, returns 401. If the cart does not exist or does not belong to the current user, returns 404."
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
        user_id = getattr(request.user, 'id', None)
        if not user_id:
            return error_response('UNAUTHORIZED', 'Authentication required')
        serializer = CartWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dto = self.service.update_cart(cart_id, serializer.validated_data, user_id=user_id)
        if not dto:
            return error_response('NOT_FOUND', 'Cart not found', {'id': str(cart_id)})
        return Response(CartReadSerializer(dto).data)
    @extend_schema(
        summary="Patch cart items",
        description=(
            "Applies add/update/remove item operations. Requires authentication and only the owner can patch their cart. "
            "If unauthenticated, returns 401. If the cart does not exist or does not belong to the current user, returns 404."
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
        user_id = getattr(request.user, 'id', None)
        if not user_id:
            return error_response('UNAUTHORIZED', 'Authentication required')
        # Interpret patch operations for cart items
        ops_serializer = CartPatchSerializer(data=request.data)
        ops_serializer.is_valid(raise_exception=True)
        dto = self.service.patch_operations(cart_id, ops_serializer.validated_data, user_id=user_id)
        if not dto:
            return error_response('NOT_FOUND', 'Cart not found', {'id': str(cart_id)})
        return Response(CartReadSerializer(dto).data)
    @extend_schema(
        summary="Delete cart",
        description=(
            "Deletes a cart. Requires authentication; only the owner (derived from the JWT in the Authorization "
            "header) can delete their cart. If unauthenticated, returns 401. If the cart does not exist or does "
            "not belong to the current user, returns 404."
        ),
        responses={
            204: None,
            401: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def delete(self, request, cart_id: int):
        user_id = getattr(request.user, 'id', None)
        if not user_id:
            return error_response('UNAUTHORIZED', 'Authentication required')
        deleted = self.service.delete_cart(cart_id, user_id=user_id)
        if not deleted:
            return error_response('NOT_FOUND', 'Cart not found', {'id': str(cart_id)})
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Carts"])
class CartByUserView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = CartService()

    @extend_schema(
        summary="List carts by user",
        parameters=[OpenApiParameter("user_id", int, OpenApiParameter.PATH)],
        responses={200: CartReadSerializer(many=True)},
    )
    def get(self, request, user_id: int):
        data = self.service.list_carts(user_id=user_id)
        serializer = CartReadSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=False)
        return Response(serializer.data)
