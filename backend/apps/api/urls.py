from django.urls import path, include
from apps.catalog.views import (
    ProductListView,
    ProductDetailView,
    CategoryListView,
    CategoryDetailView,
    ProductRatingView,
    ProductRatingListView,
)

urlpatterns = [
    path("products/", ProductListView.as_view(), name="api-products-list"),
    path(
        "products/<int:product_id>/",
        ProductDetailView.as_view(),
        name="api-products-detail",
    ),
    path(
        "products/<int:product_id>/rating/",
        ProductRatingView.as_view(),
        name="api-products-rating",
    ),
    path(
        "products/<int:product_id>/ratings/",
        ProductRatingListView.as_view(),
        name="api-products-ratings-list",
    ),
    path("categories/", CategoryListView.as_view(), name="api-categories-list"),
    path(
        "categories/<int:category_id>/",
        CategoryDetailView.as_view(),
        name="api-categories-detail",
    ),
    # Other domain groupings remain namespaced
    path("users/", include("apps.users.urls")),
    path("carts/", include("apps.carts.urls")),
    path("auth/", include("apps.auth.urls")),
]
