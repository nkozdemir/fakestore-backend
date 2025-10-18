from django.urls import path
from .views import (
    UsernameAvailabilityView,
    RegisterView,
    LoginView,
    StaffLoginView,
    RefreshView,
    MeView,
    LogoutView,
    LogoutAllView,
)

urlpatterns = [
    path(
        "validate-username/",
        UsernameAvailabilityView.as_view(),
        name="auth-validate-username",
    ),
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("login/staff/", StaffLoginView.as_view(), name="auth-staff-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("logout-all/", LogoutAllView.as_view(), name="auth-logout-all"),
]
