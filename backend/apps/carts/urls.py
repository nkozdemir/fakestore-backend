from django.urls import path
from .views import CartListView, CartDetailView

urlpatterns = [
	path('', CartListView.as_view()),
	path('<int:cart_id>/', CartDetailView.as_view()),
]
