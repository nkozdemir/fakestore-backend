from django.urls import path, include
from apps.catalog.views import ProductListView, ProductDetailView, CategoryListView, ProductByCategoriesView, ProductRatingView

urlpatterns = [
    path('products/', ProductListView.as_view()),
    path('products/<int:product_id>/', ProductDetailView.as_view()),
    path('products/<int:product_id>/rating/', ProductRatingView.as_view()),
    path('products/by-categories/', ProductByCategoriesView.as_view()),
    path('categories/', CategoryListView.as_view()),

    # Other domain groupings remain namespaced
    path('users/', include('apps.users.urls')),
    path('carts/', include('apps.carts.urls')),
]
