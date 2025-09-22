from django.urls import path
from .views import CartListView, CartDetailView, CartByUserView

urlpatterns = [
	path('', CartListView.as_view(), name='api-carts-list'),
	path('<int:cart_id>/', CartDetailView.as_view(), name='api-carts-detail'),
	# Support without trailing slash for clients using /api/carts/{id}
	path('<int:cart_id>', CartDetailView.as_view(), name='api-carts-detail-noslash'),
	path('users/<int:user_id>/', CartByUserView.as_view(), name='api-carts-by-user'),
	# Support without trailing slash for clients using /api/carts/users/{user_id}
	path('users/<int:user_id>', CartByUserView.as_view(), name='api-carts-by-user-noslash'),
]
