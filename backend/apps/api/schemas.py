from drf_spectacular.utils import inline_serializer
from rest_framework import serializers


class ErrorDetailSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    status = serializers.IntegerField()
    details = serializers.JSONField(required=False)
    hint = serializers.CharField(required=False, allow_blank=True)
    extra = serializers.JSONField(required=False)


class ErrorResponseSerializer(serializers.Serializer):
    error = ErrorDetailSerializer()


def paginated_response(
    item_serializer_class: type[serializers.Serializer],
) -> type[serializers.Serializer]:
    """Create an inline paginated response serializer with standard DRF PageNumberPagination shape.

    Returns a serializer with fields: count, next, previous, results[item_serializer].
    """
    name = getattr(item_serializer_class, "__name__", "Items")
    return inline_serializer(
        name=f"Paginated{name}",
        fields={
            "count": serializers.IntegerField(),
            "next": serializers.CharField(allow_null=True),
            "previous": serializers.CharField(allow_null=True),
            "results": item_serializer_class(many=True),
        },
    )
