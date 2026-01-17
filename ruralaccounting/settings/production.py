"""
Production settings for ruralaccounting project.
Security-hardened configuration for deployment on Railway/Render.
"""
import os
import dj_database_url
from .base import *

# Optional Sentry SDK imports
try:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

# Security settings
DEBUG = False

# SECRET_KEY must be set in environment variables
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']

# ALLOWED_HOSTS must be set in environment variables (comma-separated)
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',')
CSRF_TRUSTED_ORIGINS = [
    'https://prilika-production.up.railway.app',
    'https://*.up.railway.app',  # This covers any Railway subdomain
]

# HTTPS/Security Headers
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Database - PostgreSQL via DATABASE_URL
# Automatically set by Railway/Render when PostgreSQL is added
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,  # Connection pooling
        conn_health_checks=True,
    )
}

# Static files - WhiteNoise handles compression and serving
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Email configuration - SMTP backend
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.sendgrid.net')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)

# Admin email for notifications
ADMINS = [
    ('Admin', os.environ.get('NOTIFICATION_EMAIL', 'admin@example.com')),
]

# Sentry error tracking
if SENTRY_AVAILABLE and os.environ.get('SENTRY_DSN'):
    sentry_sdk.init(
        dsn=os.environ['SENTRY_DSN'],
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
        send_default_pii=False,  # Don't send personally identifiable information
        environment=os.environ.get('SENTRY_ENVIRONMENT', 'production'),
    )

# Structured logging for production
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.environ.get('LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'accounting': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Optional: AWS S3 for static/media files (if using CDN)
# Uncomment and configure if needed:
# if os.environ.get('AWS_STORAGE_BUCKET_NAME'):
#     INSTALLED_APPS += ['storages']
#     AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
#     AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
#     AWS_STORAGE_BUCKET_NAME = os.environ['AWS_STORAGE_BUCKET_NAME']
#     AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'ap-south-1')
#     AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
#     AWS_DEFAULT_ACL = 'public-read'
#     AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
#     STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
#     STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
