from django.urls import path
from .views import ProductListView, ProductDetailView, CategoryListView, CategoryDetailView

urlpatterns = [
	path('products/', ProductListView.as_view(), name='api-products-list'),
	path('products/<int:product_id>/', ProductDetailView.as_view(), name='api-products-detail'),
	path('categories/', CategoryListView.as_view(), name='api-categories-list'),
	path('categories/<int:category_id>/', CategoryDetailView.as_view(), name='api-categories-detail'),
]
