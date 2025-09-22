from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import CartService
from .serializers import CartReadSerializer, CartWriteSerializer
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
        parameters=[OpenApiParameter(name="user_id", description="Filter by user ID", required=False, type=int)],
        responses={200: CartReadSerializer(many=True)},
    )
    def get(self, request):
        user_id = request.query_params.get('user_id')
        data = self.service.list_carts(user_id=int(user_id)) if user_id else self.service.list_carts()
        serializer = CartReadSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=False)
        return Response(serializer.data)
    @extend_schema(
        summary="Create cart",
        request=CartWriteSerializer,
        responses={201: CartReadSerializer, 400: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def post(self, request):
        serializer = CartWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dto = self.service.create_cart(serializer.validated_data)
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
        request=CartWriteSerializer,
        responses={200: CartReadSerializer, 400: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def put(self, request, cart_id: int):
        serializer = CartWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dto = self.service.update_cart(cart_id, serializer.validated_data)
        if not dto:
            return error_response('NOT_FOUND', 'Cart not found', {'id': str(cart_id)})
        return Response(CartReadSerializer(dto).data)
    @extend_schema(
        summary="Patch cart items",
        request=CartPatchSerializer,
        responses={200: CartReadSerializer, 400: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def patch(self, request, cart_id: int):
        # Interpret patch operations for cart items
        ops_serializer = CartPatchSerializer(data=request.data)
        ops_serializer.is_valid(raise_exception=True)
        dto = self.service.patch_operations(cart_id, ops_serializer.validated_data)
        if not dto:
            return error_response('NOT_FOUND', 'Cart not found', {'id': str(cart_id)})
        return Response(CartReadSerializer(dto).data)
    @extend_schema(
        summary="Delete cart",
        responses={204: None, 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def delete(self, request, cart_id: int):
        deleted = self.service.delete_cart(cart_id)
        if not deleted:
            return error_response('NOT_FOUND', 'Cart not found', {'id': str(cart_id)})
        return Response(status=status.HTTP_204_NO_CONTENT)
