"""
Base settings for SURPLUSSYNC Django project.
Common configuration shared across all environments (dev, prod).
"""

import os
import sys
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env
# In production, environment variables should be set by the deployment platform
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG defaults to False in production, True in development
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1')

# Allowed hosts - must be set via environment variable in production
ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', '').split(',') if host.strip()]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'rest_framework',
    'corsheaders',
    'django_filters',
    'django_q',
    # Local apps
    'core',
    'accounts',
    'inventory',
    'marketplace',
    'administration',
    'predictions',
]

AUTH_USER_MODEL = 'accounts.User'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'SURPLUSSYNC.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'SURPLUSSYNC.wsgi.application'


# Database
# Use PostgreSQL when USE_POSTGRES=True in .env; falls back to SQLite for local ease

USE_POSTGRES = os.getenv('USE_POSTGRES', 'False').lower() in ('true', '1')

if USE_POSTGRES:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'surplussync'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
else:
    # SQLite for development/testing
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static and Media files

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Email configuration
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@surplussync.com')
EMAIL_ALERTS_ENABLED = os.getenv('EMAIL_ALERTS_ENABLED', 'True').lower() in ('1', 'true', 'yes')


# CORS settings
CORS_ALLOW_ALL_ORIGINS = os.getenv('CORS_ALLOW_ALL_ORIGINS', 'False').lower() in ('true', '1')
if not CORS_ALLOW_ALL_ORIGINS:
    CORS_ALLOWED_ORIGINS = [
        origin.strip() for origin in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if origin.strip()
    ]


# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'inventory.authentication.ApiKeyAuthentication',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.getenv('THROTTLE_ANON_RATE', '100/day'),
        'user': os.getenv('THROTTLE_USER_RATE', '1000/day'),
        'predictions': os.getenv('THROTTLE_PREDICTIONS_RATE', '60/minute'),
    },
    'DEFAULT_PAGINATION_CLASS': 'SURPLUSSYNC.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': int(os.getenv('PAGE_SIZE', '50')),
}

# Internal ML Microservice Configuration
ML_SERVICE_URL = os.getenv('ML_SERVICE_URL', 'http://127.0.0.1:8001')
ML_SERVICE_TOKEN = os.getenv('ML_SERVICE_TOKEN', 'surplussync-service-token-dev')
ML_SERVICE_TIMEOUT = float(os.getenv('ML_SERVICE_TIMEOUT', '3.0'))

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_LIFETIME_MINUTES', '30'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('JWT_REFRESH_LIFETIME_DAYS', '7'))),
}

# Django Q2 Cluster Configuration
Q_CLUSTER = {
    'name': 'SurplusSync',
    'workers': int(os.getenv('Q_CLUSTER_WORKERS', '2')),
    'timeout': int(os.getenv('Q_CLUSTER_TIMEOUT', '120')),
    'retry': int(os.getenv('Q_CLUSTER_RETRY', '150')),
    'max_attempts': int(os.getenv('Q_CLUSTER_MAX_ATTEMPTS', '3')),
    'save_limit': int(os.getenv('Q_CLUSTER_SAVE_LIMIT', '50')),
    'catch_up': False,
    'time_zone': 'Asia/Kolkata',
    'orm': 'default',
}

# CSV Import Configuration
IMPORT_SYNC_ROW_LIMIT = int(os.getenv('IMPORT_SYNC_ROW_LIMIT', '50'))

# Matching Engine Learning Layer Configuration
MATCHING_LEARNING_LAYER_ENABLED = os.getenv('MATCHING_LEARNING_LAYER_ENABLED', 'True').lower() in ('true', '1')
MATCHING_LEARNED_WEIGHT = float(os.getenv('MATCHING_LEARNED_WEIGHT', '0.35'))
MATCHING_MIN_REAL_REQUESTS = int(os.getenv('MATCHING_MIN_REAL_REQUESTS', '200'))
MATCHING_MODELS_DIR = os.path.join(BASE_DIR, 'marketplace', 'models_registry')
MATCHING_MODEL_PATH = os.path.join(MATCHING_MODELS_DIR, 'matching_reranker.joblib')
MATCHING_METADATA_PATH = os.path.join(MATCHING_MODELS_DIR, 'matching_reranker_metadata.json')

# Sustainability Impact & ESG Constants
IMPACT_MEAL_KG_FACTOR = float(os.getenv('IMPACT_MEAL_KG_FACTOR', '0.42'))
IMPACT_CO2E_KG_FACTOR = float(os.getenv('IMPACT_CO2E_KG_FACTOR', '2.5'))
IMPACT_WATER_L_FACTOR = float(os.getenv('IMPACT_WATER_L_FACTOR', '1000.0'))
IMPACT_FINANCIAL_VALUE_PER_KG = float(os.getenv('IMPACT_FINANCIAL_VALUE_PER_KG', '150.0'))
