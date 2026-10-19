"""
Django settings for SURPLUSSYNC project.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-n!nj69n1te+bg49tuo*w(w@2*38cn54c=e6butcvco9o-b_-u4')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1')

ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', '*').split(',') if host.strip()]


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
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST'),
            'PORT': os.getenv('DB_PORT'),
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


# Email configuration (Django 6.1 MAILERS)
MAILERS = {
    'default': {
        'BACKEND': os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend'),
    }
}
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@surplussync.com')
EMAIL_ALERTS_ENABLED = os.getenv('EMAIL_ALERTS_ENABLED', 'True').lower() in ('1', 'true', 'yes')


# CORS settings
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
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
    'DEFAULT_PAGINATION_CLASS': 'SURPLUSSYNC.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 50,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# Django Q2 Cluster Configuration
Q_CLUSTER = {
    'name': 'SurplusSync',
    'workers': 2,
    'timeout': 120,
    'retry': 150,
    'max_attempts': 3,
    'save_limit': 50,
    'catch_up': False,
    'time_zone': 'Asia/Kolkata',
    'orm': 'default',
    'sync': 'test' in sys.argv,
}

# CSV Import Configuration
IMPORT_SYNC_ROW_LIMIT = int(os.getenv('IMPORT_SYNC_ROW_LIMIT', '50'))


