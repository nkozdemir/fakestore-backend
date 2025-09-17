from django.apps import AppConfig


class AuthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.auth'
    # Use a unique label to avoid clashing with django.contrib.auth
    label = 'fakestore_auth'
