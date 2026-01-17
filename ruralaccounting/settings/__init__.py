"""
Django settings package for ruralaccounting project.

Automatically loads the appropriate settings module based on DJANGO_ENV environment variable.
- DJANGO_ENV=production -> production settings
- DJANGO_ENV=development (or unset) -> development settings
"""
import os

ENV = os.environ.get('DJANGO_ENV', 'development')

if ENV == 'production':
    from .production import *
else:
    from .development import *
