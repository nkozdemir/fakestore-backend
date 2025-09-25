from rest_framework import serializers
from .dtos import ProductDTO, CategoryDTO


class CategorySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()


class ProductReadSerializer(serializers.Serializer):
    # Matches ProductDTO shapes used for responses
    id = serializers.IntegerField()
    title = serializers.CharField()
    price = serializers.CharField()
    description = serializers.CharField()
    image = serializers.CharField()
    rate = serializers.CharField()
    count = serializers.IntegerField()
    categories = CategorySerializer(many=True)


class ProductWriteSerializer(serializers.Serializer):
    # Payload for creating/updating products
    # 'id' is server-assigned (auto increment) and MUST NOT be provided by clients.
    # Keep it out of the write serializer to avoid validation errors when omitted.
    title = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    description = serializers.CharField()
    image = serializers.CharField(allow_blank=True)
    # Optional on write; service will set M2M if provided
    rate = serializers.FloatField(required=False)
    count = serializers.IntegerField(required=False)
    categories = serializers.ListField(child=serializers.IntegerField(), required=False)
