from rest_framework import serializers
from .dtos import CartDTO, CartProductDTO
from apps.catalog.serializers import ProductReadSerializer

class CartProductSerializer(serializers.Serializer):
    product = ProductReadSerializer()
    quantity = serializers.IntegerField()

class CartReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    date = serializers.CharField()
    # Accept items in input but don't map directly to Cart model on create/update; treated by patch ops
    items = CartProductSerializer(many=True)


class CartWriteSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    user_id = serializers.IntegerField(required=False)
    date = serializers.CharField(required=False)
    # Relax validation for write payloads; service ignores items on create/update
    items = serializers.ListField(child=serializers.DictField(), required=False)


class CartCreateProductSerializer(serializers.Serializer):
    productId = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class CartCreateSerializer(serializers.Serializer):
    # POST-only serializer: camelCase contract
    # userId is inferred from the JWT-authenticated user; do not include it in the payload
    date = serializers.CharField(required=False)
    products = serializers.ListField(child=CartCreateProductSerializer(), required=False)
    # 'id' is not accepted here; it will be auto-assigned by the service
