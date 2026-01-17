"""
Django settings package for ruralaccounting project.

Automatically loads the appropriate settings module based on DEBUG environment variable.
- DEBUG=False -> production settings
- DEBUG=True (or unset) -> development settings
"""
import os

# Check DEBUG from environment (defaults to True for development)
DEBUG_MODE = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

if not DEBUG_MODE:
    from .production import *
else:
    from .development import *
