from django.urls import path
from .views import ProductListView, ProductDetailView, CategoryListView, CategoryDetailView

urlpatterns = [
	path('products/', ProductListView.as_view()),
	path('products/<int:product_id>/', ProductDetailView.as_view()),
	path('categories/', CategoryListView.as_view()),
	path('categories/<int:category_id>/', CategoryDetailView.as_view()),
]
