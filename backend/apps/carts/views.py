from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import CartService
from .serializers import CartSerializer
from apps.api.utils import error_response
from rest_framework import serializers

class CartPatchSerializer(serializers.Serializer):
    add = serializers.ListField(child=serializers.DictField(), required=False)
    update = serializers.ListField(child=serializers.DictField(), required=False)
    remove = serializers.ListField(child=serializers.IntegerField(), required=False)
    date = serializers.CharField(required=False)
    userId = serializers.IntegerField(required=False)

class CartListView(APIView):
    service = CartService()
    def get(self, request):
        user_id = request.query_params.get('user_id')
        data = self.service.list_carts(user_id=int(user_id)) if user_id else self.service.list_carts()
        serializer = CartSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=False)
        return Response(serializer.data)
    def post(self, request):
        serializer = CartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dto = self.service.create_cart(serializer.validated_data)
        return Response(CartSerializer(dto).data, status=status.HTTP_201_CREATED)

class CartDetailView(APIView):
    service = CartService()
    def get(self, request, cart_id: int):
        dto = self.service.get_cart(cart_id)
        if not dto:
            return error_response('NOT_FOUND', 'Cart not found', {'id': str(cart_id)})
        serializer = CartSerializer(dto)
        return Response(serializer.data)
    def put(self, request, cart_id: int):
        serializer = CartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dto = self.service.update_cart(cart_id, serializer.validated_data)
        if not dto:
            return error_response('NOT_FOUND', 'Cart not found', {'id': str(cart_id)})
        return Response(CartSerializer(dto).data)
    def patch(self, request, cart_id: int):
        # Interpret patch operations for cart items
        ops_serializer = CartPatchSerializer(data=request.data)
        ops_serializer.is_valid(raise_exception=True)
        dto = self.service.patch_operations(cart_id, ops_serializer.validated_data)
        if not dto:
            return error_response('NOT_FOUND', 'Cart not found', {'id': str(cart_id)})
        return Response(CartSerializer(dto).data)
    def delete(self, request, cart_id: int):
        deleted = self.service.delete_cart(cart_id)
        if not deleted:
            return error_response('NOT_FOUND', 'Cart not found', {'id': str(cart_id)})
        return Response(status=status.HTTP_204_NO_CONTENT)
