from django.contrib import admin
from django.urls import path, include
from apps.common.views import live_health, ready_health
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apps.api.urls')),
    # Health / ops
    path('health/live', live_health, name='health-live'),
    path('health/ready', ready_health, name='health-ready'),
    # OpenAPI schema and docs
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
