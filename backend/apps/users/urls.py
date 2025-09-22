from django.urls import path
from .views import UserListView, UserDetailView, UserAddressListView, UserAddressDetailView

urlpatterns = [
	path('', UserListView.as_view()),
	path('<int:user_id>/', UserDetailView.as_view()),
    	path('<int:user_id>/addresses/', UserAddressListView.as_view()),
    	path('<int:user_id>/addresses/<int:address_id>/', UserAddressDetailView.as_view()),
]
