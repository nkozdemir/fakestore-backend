from rest_framework import serializers
from .dtos import CartDTO, CartProductDTO
from apps.catalog.serializers import ProductSerializer

class CartProductSerializer(serializers.Serializer):
    product = ProductSerializer()
    quantity = serializers.IntegerField()

class CartSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    date = serializers.CharField()
    items = CartProductSerializer(many=True)
