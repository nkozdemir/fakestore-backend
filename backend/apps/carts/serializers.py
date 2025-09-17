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
    id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    date = serializers.CharField()
    # Relax validation for write payloads; service ignores items on create/update
    items = serializers.ListField(child=serializers.DictField(), required=False)
