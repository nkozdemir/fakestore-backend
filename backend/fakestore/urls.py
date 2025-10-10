from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from pathlib import Path
from apps.common.views import live_health, ready_health
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.api.urls")),
    path("health/live", live_health, name="health-live"),
    path("health/ready", ready_health, name="health-ready"),
]

# Serving strategy:
# - In DEBUG: use dynamic spectacular schema & live views.
# - In production (DEBUG False): serve pre-generated static schema file if present.
if settings.DEBUG:
    urlpatterns += [
        path("schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "docs/swagger/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path(
            "docs/redoc/",
            SpectacularRedocView.as_view(url_name="schema"),
            name="redoc",
        ),
    ]
else:
    # Static schema endpoints
    def _static_schema_response(format: str):  # pragma: no cover (simple IO)
        rel = (
            settings.OPENAPI_STATIC_JSON
            if format == "json"
            else settings.OPENAPI_STATIC_YAML
        )
        static_base = Path(settings.BASE_DIR) / "static" / "schema"
        file_path = static_base / (
            "openapi.json" if format == "json" else "openapi.yaml"
        )
        if not file_path.exists():
            return JsonResponse(
                {
                    "error": "schema_not_found",
                    "message": "Static schema not found. Run make schema-export or enable DEBUG for dynamic schema.",
                },
                status=404,
            )
        content = file_path.read_text()
        if format == "json":
            return HttpResponse(content, content_type="application/json")
        return HttpResponse(content, content_type="application/yaml")

    urlpatterns += [
        path("schema/", lambda r: _static_schema_response("json"), name="schema-json"),
        path(
            "schema.yaml", lambda r: _static_schema_response("yaml"), name="schema-yaml"
        ),
        # Swagger/Redoc still work; they will request the static JSON (configure via ?url=)
        path(
            "docs/swagger/",
            SpectacularSwaggerView.as_view(url_name="schema-json"),
            name="swagger-ui",
        ),
        path(
            "docs/redoc/",
            SpectacularRedocView.as_view(url_name="schema-json"),
            name="redoc",
        ),
    ]
