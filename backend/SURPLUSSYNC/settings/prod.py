"""
Production settings for SURPLUSSYNC Django project.

REQUIRED ENVIRONMENT VARIABLES (must be set):
- SECRET_KEY: A secure, random secret key (min 50 chars)
- ALLOWED_HOSTS: Comma-separated list of allowed hosts
- DB_NAME: PostgreSQL database name
- DB_USER: PostgreSQL database user
- DB_PASSWORD: PostgreSQL database password
- DB_HOST: PostgreSQL database host
- DB_PORT: PostgreSQL database port (default: 5432)
- USE_POSTGRES: Must be 'True' in production

OPTIONAL ENVIRONMENT VARIABLES:
- DEBUG: Must be 'False' (hardcoded below)
- CORS_ALLOWED_ORIGINS: Comma-separated list of allowed CORS origins
- EMAIL_BACKEND: Django email backend (default: console in dev, SMTP in prod)
- DEFAULT_FROM_EMAIL: Email sender address
- SECURE_PROXY_SSL_HEADER: If behind a reverse proxy (e.g., 'HTTP_X_FORWARDED_PROTO', 'https')
"""

import os
from .base import *

# SECURITY WARNING: debug must be False in production
DEBUG = False

# SECURITY WARNING: SECRET_KEY must be set via environment variable
if not SECRET_KEY or SECRET_KEY.startswith('django-insecure-'):
    raise ValueError(
        "SECRET_KEY must be set to a secure, random value in production. "
        "Generate one using: python -c 'import secrets; print(secrets.token_urlsafe(50))'"
    )

# SECURITY WARNING: ALLOWED_HOSTS must be set via environment variable
if not ALLOWED_HOSTS:
    raise ValueError(
        "ALLOWED_HOSTS must be set via environment variable in production. "
        "Example: ALLOWED_HOSTS=example.com,api.example.com"
    )

# SECURITY WARNING: Database must be PostgreSQL in production
if not os.getenv('USE_POSTGRES', 'True').lower() in ('true', '1'):
    raise ValueError(
        "USE_POSTGRES must be 'True' in production. SQLite is not supported for production use."
    )

# SECURITY: HTTPS and security headers
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = tuple(p.strip() for p in os.getenv('SECURE_PROXY_SSL_HEADER', '').split(',') if p.strip()) or None
if SECURE_PROXY_SSL_HEADER and len(SECURE_PROXY_SSL_HEADER) == 2:
    SECURE_PROXY_SSL_HEADER = (SECURE_PROXY_SSL_HEADER[0], SECURE_PROXY_SSL_HEADER[1])
else:
    SECURE_PROXY_SSL_HEADER = None

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Security middleware settings
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# Email configuration for production
if EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ('true', '1')
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
    if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
        raise ValueError(
            "EMAIL_HOST_USER and EMAIL_HOST_PASSWORD must be set when using SMTP email backend."
        )

# Logging - structured logs to stdout for containerized deployments
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s '
                      '%(module)s %(funcName)s %(filename)s %(lineno)d '
                      '%(pathname)s %(process)d %(thread)d %(request_id)s %(user_id)s',
        },
        'simple': {
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json' if os.getenv('USE_JSON_LOGGING', 'True').lower() in ('true', '1') else 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'marketplace': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'inventory': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Static files - use WhiteNoise or S3 in production
# For S3, install django-storages and configure below
STATICFILES_STORAGE = os.getenv('STATICFILES_STORAGE', 'django.contrib.staticfiles.storage.StaticFilesStorage')

# Sentry integration (optional)
if os.getenv('SENTRY_DSN'):
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=os.getenv('SENTRY_DSN'),
        environment=os.getenv('SENTRY_ENVIRONMENT', 'production'),
        traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
        profiles_sample_rate=float(os.getenv('SENTRY_PROFILES_SAMPLE_RATE', '0.1')),
        integrations=[DjangoIntegration()],
        send_default_pii=False,
    )
