import os
from datetime import timedelta
from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-wg8^fa)6f=+i4-^xhb9vkag#ow-q+&pi(tfq_2i&yu4)^k(wiz'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework.authtoken',
    'corsheaders',
    'drf_yasg',
    'django_countries',
    'app',
    'kyc',
    'iban',
]

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

ROOT_URLCONF = 'bank.urls'

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

WSGI_APPLICATION = 'bank.wsgi.application'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

# Optionally, you can define JWT settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=1440),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

CORS_ALLOW_ALL_ORIGINS = True

# CORS_ALLOWED_ORIGINS = [

#    "http://127.0.0.1:8000",  # If running Django on a different port
#    "http://localhost:61459",
# ]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",  # Allow all ports on localhost
    r"^http://127.0.0.1:\d+$",  # Allow all ports on 127.0.0.1
]

CORS_ALLOW_CREDENTIALS = True

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

# Define STATIC_ROOT to specify where static files will be collected
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / "static",  # If you have additional static directories
]

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email settings (for password reset and email verification)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.your-email-provider.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@example.com'
EMAIL_HOST_PASSWORD = 'your-email-password'

CIRCLE_API_KEY = '69942947473566b7623b7961bfbd5996:4d7135bf215a27897b846c1f24be52a6'
CIRCLE_API_SECRET = '69942947473566b7623b7961bfbd5996:4d7135bf215a27897b846c1f24be52a6'
CIRCLE_API_URL = 'https://api-sandbox.circle.com/v1/'  # Update with the correct endpoint

STELLAR_PLATFORM_SECRET = 'SCECAQJKZUNRRBILAFKF5ZPCQZK3M2BIZLUNNMFEJM2KLZ334WRU4ZTC'
STELLAR_PLATFORM_PUBLIC_KEY = 'GAZX7B22CLDK6FV4FDFHAXZDUXYASO64BCP5YRSTKOUELKGWDJXOEIHG'

USDC_ISSUER_PUBLIC_KEY = 'GADJU2EVVSDDJ5KSZFWG5PL4TG5C53H2V2S7A2Z6SBEU7DTLPPUSWZSK'

AUTH_USER_MODEL = 'app.User'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}

CELERY_BROKER_URL = 'redis://localhost:6379/0'  # Or your chosen broker
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

SERVER_JWT_KEY = '0fteaFpuDHH3J07b5BiYh8suLU_u1Sw67soOOjzgMIY'

env = environ.Env()
environ.Env.read_env()  # Loads environment variables from the .env file
