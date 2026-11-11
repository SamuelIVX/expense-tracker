"""
Settings module for running tests via pytest or test runner.
Overrides DATABASES to use an in-memory SQLite engine when MySQL is not available.
"""
import os
from expense_tracker.settings import *  # noqa: F401, F403

if 'DB_ENGINE' not in os.environ and 'CI' not in os.environ:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
