import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
# Try root project .env (one directory up from BASE_DIR) first, then local
root_env = (BASE_DIR.parent / '.env')
local_env = (BASE_DIR / '.env')
if root_env.exists():
    load_dotenv(root_env)
elif local_env.exists():
    load_dotenv(local_env)

# ---------------------------------------------------------------------------
# SECRET KEY HANDLING
# Prefer DJANGO_SECRET_KEY, fall back to SECRET_KEY for broader compatibility.
# In production (DEBUG=False) we require a non-default, non-empty key.
# ---------------------------------------------------------------------------
_candidate_key = (
    os.getenv('DJANGO_SECRET_KEY')
    or os.getenv('SECRET_KEY')
    or ''
)

# If key is blank, fall back to a deterministic dev key (only in DEBUG) so the
# server can still start locally. We'll validate right after DEBUG is computed.
SECRET_KEY = _candidate_key if _candidate_key else 'dev-secret-key'
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

# Validate SECRET_KEY (after DEBUG so we know environment context)
if (not SECRET_KEY or SECRET_KEY == 'dev-secret-key') and not DEBUG:
    raise ImproperlyConfigured(
        'SECRET_KEY is missing or using insecure default. Set DJANGO_SECRET_KEY or SECRET_KEY env var.'
    )
if not SECRET_KEY:
    # Even in DEBUG we do not allow an empty string; generation is trivial.
    raise ImproperlyConfigured(
        'SECRET_KEY must not be empty. Generate one with: '\
        "python -c 'from django.core.management.utils import get_random_secret_key as g; print(g())'"  # noqa: E501
    )

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'drf_spectacular',
    'rest_framework_simplejwt.token_blacklist',
    'apps.common',
    'apps.catalog',
    'apps.users',
    'apps.carts',
    'apps.auth.apps.AuthConfig',
]

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'FakeStore API',
    'DESCRIPTION': 'FakeStore backend API with layered architecture, JWT auth, and carts/ratings.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/api',
    'SERVE_PERMISSIONS': [],
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'fakestore.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'fakestore.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'fakestore'),
        'USER': os.getenv('POSTGRES_USER', 'fakestore'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'fakestore'),
        'HOST': os.getenv('POSTGRES_HOST', 'db'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}

# Caching (Redis by default)
"""Caching configuration.
Default REDIS_URL now points to the docker compose service name `redis` so
production/docker environments get a fast cache by default. In local non-docker
dev you can override with 127.0.0.1. We also ignore cache exceptions so cache
outages do not block request handling (trade-off: potential stampede or slower
responses until cache returns)."""
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/1')
CACHE_TTL = int(os.getenv('CACHE_TTL', '300'))  # seconds

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            # Fail open – if Redis is down, treat cache operations as no-ops.
            'IGNORE_EXCEPTIONS': True,
        },
        'KEY_PREFIX': os.getenv('CACHE_KEY_PREFIX', 'fakestore'),
        'TIMEOUT': CACHE_TTL,
    }
}

# Use SQLite for tests to simplify CI/dev without Postgres
USING_PYTEST = (
    os.getenv('PYTEST_CURRENT_TEST') is not None
    or any(os.path.basename(arg).startswith('pytest') for arg in sys.argv)
)

if 'test' in sys.argv or USING_PYTEST:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    # Use local in-memory cache during tests
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'fakestore-test-cache',
            'TIMEOUT': 60,
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = os.getenv('STATIC_ROOT', str(BASE_DIR / 'staticfiles'))
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
OPENAPI_STATIC_JSON = 'schema/openapi.json'
OPENAPI_STATIC_YAML = 'schema/openapi.yaml'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Use custom user model
AUTH_USER_MODEL = 'users.User'
