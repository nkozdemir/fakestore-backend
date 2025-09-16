from rest_framework import serializers
from .dtos import ProductDTO, CategoryDTO

class CategorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()

class ProductSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    price = serializers.CharField()
    description = serializers.CharField()
    image = serializers.CharField()
    rate = serializers.CharField()
    count = serializers.IntegerField()
    categories = CategorySerializer(many=True)
