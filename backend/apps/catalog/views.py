from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from .container import build_product_service, build_category_service
from .serializers import (
    ProductReadSerializer,
    ProductWriteSerializer,
    CategorySerializer,
    ProductRatingsListSerializer,
)
from apps.api.utils import error_response
from .pagination import ProductListPagination
from apps.common import get_logger
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from apps.api.schemas import paginated_response, ErrorResponseSerializer
from .mappers import ProductMapper

logger = get_logger(__name__).bind(component="catalog", layer="view")


def _ensure_admin_privileged(log, request, action: str, resource: str):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        log.warning(
            "Unauthorized action attempt",
            resource=resource,
            action=action,
        )
        return error_response("UNAUTHORIZED", "Authentication required")
    if not (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)):
        log.warning(
            "Forbidden action",
            resource=resource,
            action=action,
            user_id=getattr(user, "id", None),
        )
        return error_response(
            "FORBIDDEN", f"You do not have permission to manage {resource}"
        )
    return None


def _ensure_category_privileged(log, request, action: str):
    return _ensure_admin_privileged(log, request, action, "categories")


def _ensure_product_privileged(log, request, action: str):
    return _ensure_admin_privileged(log, request, action, "products")


@extend_schema(tags=["Catalog"])
class ProductListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = build_product_service()
    log = logger.bind(view="ProductListView")

    @extend_schema(
        operation_id="products_list",
        summary="List products",
        description="Supports pagination via ?page and ?limit. Cached results may be served.",
        parameters=[
            OpenApiParameter(
                name="category",
                description="Filter by category name",
                required=False,
                type=str,
            )
        ],
        responses={200: paginated_response(ProductReadSerializer)},
    )
    def get(self, request):
        category = request.query_params.get("category")
        self.log.debug("Handling product list request", category=category)
        queryset = self.service.products_queryset(category=category)
        paginator = ProductListPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        dtos = ProductMapper.many_to_dto(page)
        serializer = ProductReadSerializer(dtos, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        summary="Create product",
        request=ProductWriteSerializer,
        responses={
            201: ProductReadSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def post(self, request):
        guard = _ensure_product_privileged(self.log, request, "create")
        if guard:
            return guard
        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.log.info(
            "Creating product via API", title=serializer.validated_data.get("title")
        )
        dto = self.service.create_product(serializer.validated_data)
        out = ProductReadSerializer(dto).data
        product_id = getattr(dto, "id", None)
        if product_id is None and isinstance(dto, dict):
            product_id = dto.get("id")
        self.log.info("Product created via API", product_id=product_id)
        return Response(out, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Catalog"])
class ProductDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = build_product_service()
    log = logger.bind(view="ProductDetailView")

    @extend_schema(
        operation_id="products_retrieve",
        summary="Get product",
        parameters=[OpenApiParameter("product_id", int, OpenApiParameter.PATH)],
        responses={
            200: ProductReadSerializer,
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def get(self, request, product_id: int):
        self.log.debug("Fetching product detail", product_id=product_id)
        dto = self.service.get_product(product_id)
        if not dto:
            self.log.info("Product not found", product_id=product_id)
            return error_response(
                "NOT_FOUND", "Product not found", {"id": str(product_id)}
            )
        return Response(ProductReadSerializer(dto).data)

    @extend_schema(
        summary="Replace product",
        request=ProductWriteSerializer,
        responses={
            200: ProductReadSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def put(self, request, product_id: int):
        guard = _ensure_product_privileged(self.log, request, "replace")
        if guard:
            return guard
        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.log.info("Replacing product", product_id=product_id)
        dto = self.service.update_product(
            product_id, serializer.validated_data, partial=False
        )
        if not dto:
            self.log.warning("Product replace failed: not found", product_id=product_id)
            return error_response(
                "NOT_FOUND", "Product not found", {"id": str(product_id)}
            )
        return Response(ProductReadSerializer(dto).data)

    @extend_schema(
        summary="Update product",
        request=ProductWriteSerializer,
        responses={
            200: ProductReadSerializer,
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def patch(self, request, product_id: int):
        guard = _ensure_product_privileged(self.log, request, "patch")
        if guard:
            return guard
        self.log.info("Patching product", product_id=product_id)
        dto_existing = self.service.get_product(product_id)
        if not dto_existing:
            self.log.info("Product not found for patch", product_id=product_id)
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProductWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        dto = self.service.update_product(
            product_id, serializer.validated_data, partial=True
        )
        return Response(ProductReadSerializer(dto).data)

    @extend_schema(
        summary="Delete product",
        responses={204: None, 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def delete(self, request, product_id: int):
        guard = _ensure_product_privileged(self.log, request, "delete")
        if guard:
            return guard
        self.log.info("Deleting product", product_id=product_id)
        deleted = self.service.delete_product(product_id)
        if not deleted:
            self.log.warning("Product delete failed: not found", product_id=product_id)
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Catalog"])
class CategoryListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = build_category_service()
    log = logger.bind(view="CategoryListView")

    @extend_schema(
        summary="List categories", responses={200: CategorySerializer(many=True)}
    )
    def get(self, request):
        self.log.debug("Listing categories")
        data = self.service.list_categories()
        return Response(CategorySerializer(data, many=True).data)

    @extend_schema(
        summary="Create category",
        request=CategorySerializer,
        responses={
            201: CategorySerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def post(self, request):
        guard = _ensure_category_privileged(self.log, request, "create")
        if guard:
            return guard
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.log.info("Creating category", name=serializer.validated_data.get("name"))
        dto = self.service.create_category(serializer.validated_data)
        category_id = getattr(dto, "id", None)
        if category_id is None and isinstance(dto, dict):
            category_id = dto.get("id")
        self.log.info("Category created", category_id=category_id)
        return Response(CategorySerializer(dto).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Catalog"])
class CategoryDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = build_category_service()
    log = logger.bind(view="CategoryDetailView")

    @extend_schema(
        summary="Get category",
        parameters=[OpenApiParameter("category_id", int, OpenApiParameter.PATH)],
        responses={
            200: CategorySerializer,
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def get(self, request, category_id: int):
        self.log.debug("Fetching category detail", category_id=category_id)
        dto = self.service.get_category(category_id)
        if not dto:
            self.log.info("Category not found", category_id=category_id)
            return error_response(
                "NOT_FOUND", "Category not found", {"id": str(category_id)}
            )
        return Response(CategorySerializer(dto).data)

    @extend_schema(
        summary="Replace category",
        request=CategorySerializer,
        responses={
            200: CategorySerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def put(self, request, category_id: int):
        guard = _ensure_category_privileged(self.log, request, "replace")
        if guard:
            return guard
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.log.info("Replacing category", category_id=category_id)
        dto = self.service.update_category(category_id, serializer.validated_data)
        if not dto:
            self.log.warning(
                "Category replace failed: not found", category_id=category_id
            )
            return error_response(
                "NOT_FOUND", "Category not found", {"id": str(category_id)}
            )
        return Response(CategorySerializer(dto).data)

    @extend_schema(
        summary="Update category",
        request=CategorySerializer,
        responses={
            200: CategorySerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def patch(self, request, category_id: int):
        guard = _ensure_category_privileged(self.log, request, "patch")
        if guard:
            return guard
        serializer = CategorySerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.log.info("Patching category", category_id=category_id)
        dto = self.service.update_category(category_id, serializer.validated_data)
        if not dto:
            self.log.warning(
                "Category patch failed: not found", category_id=category_id
            )
            return error_response(
                "NOT_FOUND", "Category not found", {"id": str(category_id)}
            )
        return Response(CategorySerializer(dto).data)

    @extend_schema(
        summary="Delete category",
        responses={204: None, 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def delete(self, request, category_id: int):
        guard = _ensure_category_privileged(self.log, request, "delete")
        if guard:
            return guard
        self.log.info("Deleting category", category_id=category_id)
        deleted = self.service.delete_category(category_id)
        if not deleted:
            self.log.warning(
                "Category delete failed: not found", category_id=category_id
            )
            return error_response(
                "NOT_FOUND", "Category not found", {"id": str(category_id)}
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Catalog", "Ratings"])
class ProductRatingListView(APIView):
    permission_classes = [AllowAny]
    service = build_product_service()
    log = logger.bind(view="ProductRatingListView")

    @extend_schema(
        summary="List product ratings",
        parameters=[
            OpenApiParameter(
                "product_id",
                int,
                OpenApiParameter.PATH,
                description="Target product identifier",
            )
        ],
        responses={
            200: ProductRatingsListSerializer,
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def get(self, request, product_id: int):
        user = getattr(request, "user", None)
        self.log.debug(
            "Listing product ratings",
            product_id=product_id,
            actor_id=getattr(user, "id", None) if user else None,
        )
        result = self.service.list_product_ratings(product_id)
        if isinstance(result, tuple):
            code, msg, details = result
            self.log.warning(
                "Product ratings list failed",
                product_id=product_id,
                code=code,
                detail=msg,
            )
            return error_response(code, msg, details)
        serializer = ProductRatingsListSerializer(result)
        return Response(serializer.data)


@extend_schema(tags=["Catalog", "Ratings"])
class ProductRatingView(APIView):
    permission_classes = [IsAuthenticated]
    service = build_product_service()
    log = logger.bind(view="ProductRatingView")

    def _current_user_id(self, request):
        return getattr(request, "rating_user_id", None)

    @extend_schema(
        summary="Get rating summary",
        parameters=[
            OpenApiParameter(
                name="userId",
                description=(
                    "User ID override. Required for anonymous callers and available "
                    "to privileged users to view ratings on behalf of others."
                ),
                required=False,
                type=int,
            )
        ],
        responses={
            200: None,
            400: OpenApiResponse(response=ErrorResponseSerializer),
            403: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def get(self, request, product_id: int):
        user_id = self._current_user_id(request)
        user = getattr(request, "user", None)
        actor_id = getattr(user, "id", None)
        is_privileged = bool(
            getattr(request, "is_privileged_user", False)
            or getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
        )
        target_user_id = user_id
        raw_user_id = request.query_params.get("userId") or request.query_params.get(
            "user_id"
        )
        if raw_user_id is not None:
            try:
                desired_user_id = int(raw_user_id)
            except (TypeError, ValueError):
                self.log.warning(
                    "Invalid userId query parameter provided for rating summary",
                    product_id=product_id,
                    actor_id=actor_id,
                    raw_value=raw_user_id,
                )
                return error_response(
                    "VALIDATION_ERROR",
                    "userId must be an integer",
                    {"userId": raw_user_id},
                )
            if is_privileged:
                target_user_id = desired_user_id
            elif user_id is None or desired_user_id != user_id:
                self.log.warning(
                    "Rating summary forbidden for non-privileged override",
                    product_id=product_id,
                    actor_id=actor_id,
                    requested_user_id=desired_user_id,
                    resolved_user_id=user_id,
                )
                return error_response(
                    "FORBIDDEN",
                    "You do not have permission to view ratings for other users",
                    {"userId": str(desired_user_id)},
                )
        self.log.debug(
            "Fetching rating summary",
            product_id=product_id,
            user_id=target_user_id,
            actor_id=actor_id,
            privileged=is_privileged,
        )
        summary = self.service.get_rating_summary(product_id, target_user_id)
        if summary is None:
            self.log.info(
                "Rating summary failed: product not found", product_id=product_id
            )
            return error_response(
                "NOT_FOUND", "Product not found", {"id": str(product_id)}
            )
        return Response(summary)

    @extend_schema(
        summary="Set user rating",
        parameters=[
            OpenApiParameter(
                name="userId",
                description=(
                    "User ID override. Required for anonymous callers and available "
                    "to privileged users to rate on behalf of others."
                ),
                required=False,
                type=int,
            )
        ],
        request=None,
        responses={
            201: None,
            400: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def post(self, request, product_id: int):
        user_id = self._current_user_id(request)
        user = getattr(request, "user", None)
        actor_id = getattr(user, "id", None)
        is_privileged = bool(
            getattr(request, "is_privileged_user", False)
            or getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
        )
        target_user_id = user_id
        raw_user_id = request.query_params.get("userId") or request.query_params.get(
            "user_id"
        )
        if raw_user_id is not None:
            try:
                desired_user_id = int(raw_user_id)
            except (TypeError, ValueError):
                self.log.warning(
                    "Invalid userId query parameter provided for rating",
                    product_id=product_id,
                    actor_id=actor_id,
                    raw_value=raw_user_id,
                )
                return error_response(
                    "VALIDATION_ERROR",
                    "userId must be an integer",
                    {"userId": raw_user_id},
                )
            if is_privileged:
                target_user_id = desired_user_id
            elif user_id is None or desired_user_id != user_id:
                self.log.warning(
                    "Rating creation forbidden for non-privileged override",
                    product_id=product_id,
                    actor_id=actor_id,
                    requested_user_id=desired_user_id,
                    resolved_user_id=user_id,
                )
                return error_response(
                    "FORBIDDEN",
                    "You do not have permission to rate on behalf of other users",
                    {"userId": str(desired_user_id)},
                )
        if target_user_id is None:
            self.log.warning(
                "Rating creation missing user identifier",
                product_id=product_id,
                actor_id=actor_id,
            )
            return error_response(
                "VALIDATION_ERROR", "Authentication required", {"userId": None}
            )
        value = request.data.get("value")
        try:
            value = int(value)
        except (TypeError, ValueError):
            self.log.warning(
                "Invalid rating payload",
                product_id=product_id,
                user_id=target_user_id,
                value=value,
            )
            return error_response(
                "VALIDATION_ERROR", "value must be between 0 and 5", {"value": value}
            )
        self.log.info(
            "Setting product rating",
            product_id=product_id,
            user_id=target_user_id,
            actor_id=actor_id,
            privileged=is_privileged,
            value=value,
        )
        result = self.service.set_user_rating(product_id, target_user_id, value)
        if isinstance(result, tuple):
            code, msg, details = result
            self.log.warning(
                "Rating update failed",
                product_id=product_id,
                user_id=target_user_id,
                code=code,
                detail=msg,
            )
            return error_response(code, msg, details)
        return Response(result, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Delete rating",
        parameters=[
            OpenApiParameter(
                name="ratingId",
                description="Rating identifier to delete",
                required=True,
                type=int,
            )
        ],
        responses={
            200: None,
            400: OpenApiResponse(response=ErrorResponseSerializer),
            403: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def delete(self, request, product_id: int):
        user_id = self._current_user_id(request)
        user = getattr(request, "user", None)
        actor_id = getattr(user, "id", None)
        is_privileged = bool(
            getattr(request, "is_privileged_user", False)
            or getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
        )
        raw_rating_id = request.query_params.get("ratingId") or request.query_params.get(
            "rating_id"
        )
        if raw_rating_id is None:
            self.log.warning(
                "Rating delete missing identifier",
                product_id=product_id,
                actor_id=actor_id,
            )
            return error_response(
                "VALIDATION_ERROR", "ratingId is required", {"ratingId": None}
            )
        try:
            rating_id = int(raw_rating_id)
        except (TypeError, ValueError):
            self.log.warning(
                "Invalid ratingId parameter",
                product_id=product_id,
                actor_id=actor_id,
                raw_value=raw_rating_id,
            )
            return error_response(
                "VALIDATION_ERROR",
                "ratingId must be an integer",
                {"ratingId": raw_rating_id},
            )
        effective_actor_id = user_id if user_id is not None else actor_id
        self.log.info(
            "Deleting rating",
            product_id=product_id,
            rating_id=rating_id,
            actor_id=effective_actor_id,
            privileged=is_privileged,
        )
        result = self.service.delete_rating(
            product_id, rating_id, effective_actor_id, is_privileged
        )
        if isinstance(result, tuple):
            code, msg, details = result
            self.log.warning(
                "Rating delete failed",
                product_id=product_id,
                rating_id=rating_id,
                actor_id=effective_actor_id,
                code=code,
                detail=msg,
            )
            return error_response(code, msg, details)
        return Response(result, status=status.HTTP_200_OK)
