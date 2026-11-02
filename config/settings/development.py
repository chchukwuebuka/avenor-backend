from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# Optional fallback to SQLite if PostgreSQL database is not yet created during early check
FALLBACK_SQLITE = os.getenv('USE_SQLITE_FALLBACK', 'False').lower() in ('true', '1', 'yes')
if FALLBACK_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
