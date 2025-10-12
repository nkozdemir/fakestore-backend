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
    # Authenticated address endpoints (self or superuser-managed)
    path("<int:user_id>/addresses/", UserAddressListView.as_view()),
    path("addresses/<int:address_id>/", UserAddressDetailView.as_view()),
]
