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


class CartItemWriteSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class CartWriteSerializer(serializers.Serializer):

    id = serializers.IntegerField(required=False)
    user_id = serializers.IntegerField(required=False)
    date = serializers.CharField(required=False)
    # Relax validation for write payloads; service ignores items on create/update
    items = CartItemWriteSerializer(many=True, required=False)


class CartCreateProductSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class CartCreateSerializer(serializers.Serializer):
    # POST-only serializer: snake_case items; userId remains to support admin overrides.
    date = serializers.CharField(required=False)
    products = serializers.ListField(
        child=CartCreateProductSerializer(), required=False
    )
    userId = serializers.IntegerField(required=False)
    # 'id' is not accepted here; it will be auto-assigned by the service
