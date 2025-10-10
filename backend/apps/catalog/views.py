from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from .container import build_product_service, build_category_service
from .serializers import ProductReadSerializer, ProductWriteSerializer, CategorySerializer
from apps.api.utils import error_response
from .pagination import ProductListPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from apps.api.schemas import paginated_response, ErrorResponseSerializer

@extend_schema(tags=["Catalog"])
class ProductListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = build_product_service()
    @extend_schema(
        operation_id="products_list",
        summary="List products",
        description="Supports pagination via ?page and ?limit. Cached results may be served.",
        parameters=[OpenApiParameter(name="category", description="Filter by category name", required=False, type=str)],
        responses={200: paginated_response(ProductReadSerializer)},
    )
    def get(self, request):
        category = request.query_params.get('category')
        # Fetch all DTOs (list of dicts) then paginate the list in-memory
        data = self.service.list_products(category=category)
        paginator = ProductListPagination()
        page = paginator.paginate_queryset(data, request, view=self)
        # Serializer expects DTO instances; pass as instance, not data
        serializer = ProductReadSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        summary="Create product",
        request=ProductWriteSerializer,
        responses={201: ProductReadSerializer, 400: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def post(self, request):
        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dto = self.service.create_product(serializer.validated_data)
        out = ProductReadSerializer(dto).data
        return Response(out, status=status.HTTP_201_CREATED)

@extend_schema(tags=["Catalog"])
class ProductDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = build_product_service()
    @extend_schema(
        operation_id="products_retrieve",
        summary="Get product",
        parameters=[OpenApiParameter("product_id", int, OpenApiParameter.PATH)],
        responses={200: ProductReadSerializer, 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def get(self, request, product_id: int):
        dto = self.service.get_product(product_id)
        if not dto:
            return error_response('NOT_FOUND', 'Product not found', {'id': str(product_id)})
        return Response(ProductReadSerializer(dto).data)

    @extend_schema(
        summary="Replace product",
        request=ProductWriteSerializer,
        responses={200: ProductReadSerializer, 400: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def put(self, request, product_id: int):
        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dto = self.service.update_product(product_id, serializer.validated_data, partial=False)
        if not dto:
            return error_response('NOT_FOUND', 'Product not found', {'id': str(product_id)})
        return Response(ProductReadSerializer(dto).data)

    @extend_schema(
        summary="Update product",
        request=ProductWriteSerializer,
        responses={200: ProductReadSerializer, 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def patch(self, request, product_id: int):
        dto_existing = self.service.get_product(product_id)
        if not dto_existing:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProductWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        dto = self.service.update_product(product_id, serializer.validated_data, partial=True)
        return Response(ProductReadSerializer(dto).data)

    @extend_schema(
        summary="Delete product",
        responses={204: None, 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def delete(self, request, product_id: int):
        deleted = self.service.delete_product(product_id)
        if not deleted:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

@extend_schema(tags=["Catalog"])
class CategoryListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = build_category_service()
    @extend_schema(summary="List categories", responses={200: CategorySerializer(many=True)})
    def get(self, request):
        data = self.service.list_categories()
        return Response(CategorySerializer(data, many=True).data)
    @extend_schema(summary="Create category", request=CategorySerializer, responses={201: CategorySerializer, 400: OpenApiResponse(response=ErrorResponseSerializer)})
    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dto = self.service.create_category(serializer.validated_data)
        return Response(CategorySerializer(dto).data, status=status.HTTP_201_CREATED)

@extend_schema(tags=["Catalog"])
class CategoryDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = build_category_service()

    @extend_schema(summary="Get category", parameters=[OpenApiParameter("category_id", int, OpenApiParameter.PATH)], responses={200: CategorySerializer, 404: OpenApiResponse(response=ErrorResponseSerializer)})
    def get(self, request, category_id: int):
        dto = self.service.get_category(category_id)
        if not dto:
            return error_response('NOT_FOUND', 'Category not found', {'id': str(category_id)})
        return Response(CategorySerializer(dto).data)

    @extend_schema(summary="Replace category", request=CategorySerializer, responses={200: CategorySerializer, 400: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)})
    def put(self, request, category_id: int):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dto = self.service.update_category(category_id, serializer.validated_data)
        if not dto:
            return error_response('NOT_FOUND', 'Category not found', {'id': str(category_id)})
        return Response(CategorySerializer(dto).data)

    @extend_schema(summary="Update category", request=CategorySerializer, responses={200: CategorySerializer, 400: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)})
    def patch(self, request, category_id: int):
        serializer = CategorySerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        dto = self.service.update_category(category_id, serializer.validated_data)
        if not dto:
            return error_response('NOT_FOUND', 'Category not found', {'id': str(category_id)})
        return Response(CategorySerializer(dto).data)

    @extend_schema(summary="Delete category", responses={204: None, 404: OpenApiResponse(response=ErrorResponseSerializer)})
    def delete(self, request, category_id: int):
        deleted = self.service.delete_category(category_id)
        if not deleted:
            return error_response('NOT_FOUND', 'Category not found', {'id': str(category_id)})
        return Response(status=status.HTTP_204_NO_CONTENT)

@extend_schema(tags=["Catalog", "Ratings"])
class ProductRatingView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = build_product_service()

    def _current_user_id(self, request):
        return getattr(request, 'rating_user_id', None)

    @extend_schema(
        summary="Get rating summary",
        parameters=[OpenApiParameter(name="userId", description="User ID (optional fallback when not authenticated)", required=False, type=int)],
        responses={200: None, 404: OpenApiResponse(response=ErrorResponseSerializer)}
    )
    def get(self, request, product_id: int):
        user_id = self._current_user_id(request)
        summary = self.service.get_rating_summary(product_id, user_id)
        if summary is None:
            return error_response('NOT_FOUND', 'Product not found', {'id': str(product_id)})
        return Response(summary)

    @extend_schema(
        summary="Set user rating",
        parameters=[OpenApiParameter(name="userId", description="User ID (optional fallback when not authenticated)", required=False, type=int)],
        request=None,
        responses={201: None, 400: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)}
    )
    def post(self, request, product_id: int):
        user_id = self._current_user_id(request)
        value = request.data.get('value')
        try:
            value = int(value)
        except (TypeError, ValueError):
            return error_response('VALIDATION_ERROR', 'value must be between 0 and 5', {'value': value})
        result = self.service.set_user_rating(product_id, user_id, value)
        if isinstance(result, tuple):
            code, msg, details = result
            return error_response(code, msg, details)
        return Response(result, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Delete user rating",
        parameters=[OpenApiParameter(name="userId", description="User ID (optional fallback when not authenticated)", required=False, type=int)],
        responses={200: None, 400: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)}
    )
    def delete(self, request, product_id: int):
        user_id = self._current_user_id(request)
        result = self.service.delete_user_rating(product_id, user_id)
        if isinstance(result, tuple):
            code, msg, details = result
            return error_response(code, msg, details)
        return Response(result, status=status.HTTP_200_OK)

@extend_schema(tags=["Catalog"])
class ProductByCategoriesView(APIView):
    permission_classes = [AllowAny]
    service = build_product_service()
    @extend_schema(
        summary="List products by categories",
        parameters=[OpenApiParameter(name="categoryIds", description="Comma-separated category IDs (camelCase)", required=True, type=str)],
        responses={200: ProductReadSerializer(many=True), 400: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def get(self, request):
        ids = getattr(request, 'category_ids', [])
        if not ids:
            return Response([])
        data = self.service.list_products_by_category_ids(ids)
        return Response(ProductReadSerializer(data, many=True).data)
