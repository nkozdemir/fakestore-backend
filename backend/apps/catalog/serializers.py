from rest_framework import serializers
from .dtos import ProductDTO, CategoryDTO


class CategorySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()

    def to_representation(self, instance):
        # Support dataclass DTO or dict
        if instance is None:
            return None
        if hasattr(instance, "__dataclass_fields__"):
            return {
                "id": getattr(instance, "id"),
                "name": getattr(instance, "name"),
            }
        # Fallback to default (e.g., if a model or dict already)
        return super().to_representation(instance)


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

    def to_representation(self, instance):
        if instance is None:
            return None
        # If it's already a dataclass DTO, extract attributes directly for speed
        if hasattr(instance, "__dataclass_fields__"):
            return {
                "id": getattr(instance, "id"),
                "title": getattr(instance, "title"),
                "price": getattr(instance, "price"),
                "description": getattr(instance, "description"),
                "image": getattr(instance, "image"),
                "rate": getattr(instance, "rate"),
                "count": getattr(instance, "count"),
                "categories": CategorySerializer(
                    getattr(instance, "categories"), many=True
                ).data,
            }
        return super().to_representation(instance)


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


class ProductRatingUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    firstName = serializers.CharField(required=False, allow_null=True)
    lastName = serializers.CharField(required=False, allow_null=True)
    value = serializers.IntegerField()
    createdAt = serializers.CharField(required=False, allow_null=True)
    updatedAt = serializers.CharField(required=False, allow_null=True)


class ProductRatingsListSerializer(serializers.Serializer):
    productId = serializers.IntegerField()
    count = serializers.IntegerField()
    ratings = ProductRatingUserSerializer(many=True)
