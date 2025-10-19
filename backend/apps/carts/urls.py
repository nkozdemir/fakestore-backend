from django.urls import path, re_path
from .views import CartListView, CartDetailView

urlpatterns = [
    path("", CartListView.as_view(), name="api-carts-list"),
    # Single pattern that accepts optional trailing slash for detail
    re_path(r"^(?P<cart_id>\d+)/?$", CartDetailView.as_view(), name="api-carts-detail"),
]
