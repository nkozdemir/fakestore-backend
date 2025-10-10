from django.urls import path, re_path
from .views import CartListView, CartDetailView, CartByUserView

urlpatterns = [
    path("", CartListView.as_view(), name="api-carts-list"),
    # Single pattern that accepts optional trailing slash for detail
    re_path(r"^(?P<cart_id>\d+)/?$", CartDetailView.as_view(), name="api-carts-detail"),
    # Single pattern that accepts optional trailing slash for by-user
    re_path(
        r"^users/(?P<user_id>\d+)/?$",
        CartByUserView.as_view(),
        name="api-carts-by-user",
    ),
]
