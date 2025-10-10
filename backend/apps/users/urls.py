from django.urls import path
from .views import (
    UserListView,
    UserDetailView,
    UserAddressListView,
    UserAddressDetailView,
)

urlpatterns = [
    path("", UserListView.as_view()),
    path("<int:user_id>/", UserDetailView.as_view()),
    # Authenticated self-scoped address endpoints
    path("me/addresses/", UserAddressListView.as_view()),
    path("me/addresses/<int:address_id>/", UserAddressDetailView.as_view()),
]
