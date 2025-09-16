from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import ProductService, CategoryService
from .serializers import ProductSerializer, CategorySerializer
from apps.api.utils import error_response

class ProductListView(APIView):
    service = ProductService()
    def get(self, request):
        category = request.query_params.get('category')
        data = self.service.list_products(category=category)
        serializer = ProductSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=False)
        return Response(serializer.data)

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dto = self.service.create_product(serializer.validated_data)
        out = ProductSerializer(dto).data
        return Response(out, status=status.HTTP_201_CREATED)

class ProductDetailView(APIView):
    service = ProductService()
    def get(self, request, product_id: int):
        dto = self.service.get_product(product_id)
        if not dto:
            return error_response('NOT_FOUND', 'Product not found', {'id': str(product_id)})
        serializer = ProductSerializer(dto)
        return Response(serializer.data)

    def put(self, request, product_id: int):
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dto = self.service.update_product(product_id, serializer.validated_data, partial=False)
        if not dto:
            return error_response('NOT_FOUND', 'Product not found', {'id': str(product_id)})
        return Response(ProductSerializer(dto).data)

    def patch(self, request, product_id: int):
        dto_existing = self.service.get_product(product_id)
        if not dto_existing:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProductSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        dto = self.service.update_product(product_id, serializer.validated_data, partial=True)
        return Response(ProductSerializer(dto).data)

    def delete(self, request, product_id: int):
        deleted = self.service.delete_product(product_id)
        if not deleted:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

class CategoryListView(APIView):
    service = CategoryService()
    def get(self, request):
        data = self.service.list_categories()
        serializer = CategorySerializer(data=data, many=True)
        serializer.is_valid(raise_exception=False)
        return Response(serializer.data)
    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dto = self.service.create_category(serializer.validated_data)
        return Response(CategorySerializer(dto).data, status=status.HTTP_201_CREATED)

class CategoryDetailView(APIView):
    service = CategoryService()

class ProductByCategoriesView(APIView):
    service = ProductService()
    def get(self, request):
        raw = request.query_params.get('categoryIds')
        if not raw:
            # Return empty list if not provided (could alternatively error)
            return Response([])
        try:
            ids = [int(x) for x in raw.split(',') if x.strip()]
        except ValueError:
            return error_response('VALIDATION_ERROR', 'Invalid categoryIds parameter', {'categoryIds': raw})
        if not ids:
            return Response([])
        data = self.service.list_products_by_category_ids(ids)
        serializer = ProductSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=False)
        return Response(serializer.data)
    def get(self, request, category_id: int):
        dto = self.service.get_category(category_id)
        if not dto:
            return error_response('NOT_FOUND', 'Category not found', {'id': str(category_id)})
        return Response(CategorySerializer(dto).data)
    def put(self, request, category_id: int):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dto = self.service.update_category(category_id, serializer.validated_data)
        if not dto:
            return error_response('NOT_FOUND', 'Category not found', {'id': str(category_id)})
        return Response(CategorySerializer(dto).data)
    def patch(self, request, category_id: int):
        serializer = CategorySerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        dto = self.service.update_category(category_id, serializer.validated_data)
        if not dto:
            return error_response('NOT_FOUND', 'Category not found', {'id': str(category_id)})
        return Response(CategorySerializer(dto).data)
    def delete(self, request, category_id: int):
        deleted = self.service.delete_category(category_id)
        if not deleted:
            return error_response('NOT_FOUND', 'Category not found', {'id': str(category_id)})
        return Response(status=status.HTTP_204_NO_CONTENT)
