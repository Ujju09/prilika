"""
WSGI config for ruralaccounting project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

try:
    import dotenv
    # Load .env from project root (one level up from this file)
    dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
except ImportError:
    pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ruralaccounting.settings')

application = get_wsgi_application()
