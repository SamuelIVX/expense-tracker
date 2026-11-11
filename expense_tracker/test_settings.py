"""
Settings module for running tests via in-memory SQLite.
Overrides DATABASES to use an in-memory SQLite engine unless DB_ENGINE is explicitly configured for MySQL.
"""
import os
from expense_tracker.settings import *  # noqa: F401, F403

_engine = os.environ.get('DB_ENGINE', '').strip().lower()
if _engine not in ('mysql', 'django.db.backends.mysql'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
