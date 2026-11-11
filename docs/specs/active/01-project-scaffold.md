# Spec: Project Scaffold

## Applicable Skills
- `owasp-security`: A02 Security Misconfiguration, environment isolation, secure cookie configuration.
- `codebase-design`: Clean project boundaries, modular settings, and explicit contract seams.

## Objective
Establish the project foundation from commit #1: initialize the local git repository (`expense-tracker`),
configure an isolated Python virtual environment (`.venv`), scaffold a standard Django 5 project
(`expense_tracker/`) with an application package (`tracker/`), connect to the local MySQL server
using `pymysql`, configure environment-based secrets via `python-dotenv`, and verify connectivity
with a smoke-test route. No business logic lives here; this is pure infrastructure.

## Scope
- Package: `expense-tracker` (new project root)
- Modifies (creates):
  - `.gitignore` (excludes `.venv/`, `.env`, `*.pyc`, `__pycache__/`, `db.sqlite3`)
  - `.env.example` (committed; keys present, values blank)
  - `.env` (git-ignored; local credentials)
  - `requirements.txt` (`Django>=5.0`, `pymysql>=1.1.0`, `python-dotenv>=1.0.0`)
  - `manage.py` (Django management entrypoint)
  - `expense_tracker/__init__.py` (executes `pymysql.install_as_MySQLdb()`)
  - `expense_tracker/settings.py` (configured for MySQL, templates, static files, and dotenv)
  - `expense_tracker/urls.py` (root URL router, includes `tracker.urls`)
  - `expense_tracker/wsgi.py`
  - `tracker/__init__.py`
  - `tracker/apps.py` (`TrackerConfig`)
  - `tracker/urls.py` (app-level URL router with smoke-test `/`)
  - `tracker/views.py` (smoke-test view)
  - `templates/` (root template directory placeholder)
  - `static/css/`, `static/js/` (static asset placeholders)
- Off-limits: Database tables and models (owned by `02-database-schema`); CSS tokens and base template (owned by `03-frontend-design-system`); authentication views (owned by `04-user-auth`).

## Non-Goals
- No custom database models or migrations beyond Django's initial system setup (see `02-database-schema`).
- No UI styling or navigation layouts (see `03-frontend-design-system`).
- No user login, registration, or session workflows (see `04-user-auth`).

## Invariants
- The virtual environment directory (`.venv/`) MUST NEVER be tracked in git. [Tooling hygiene]
- All sensitive credentials (`SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`) MUST be loaded from environment variables via `python-dotenv` — zero hardcoded credentials in source control. [OWASP A02 / ASVS 14.3.3]
- The MySQL connection driver MUST use `pymysql` via `pymysql.install_as_MySQLdb()` in `expense_tracker/__init__.py` to avoid native compilation issues on macOS and Windows machines. [Portability]
- Cookie security flags MUST be configured: `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = 'Lax'`, `CSRF_COOKIE_SAMESITE = 'Lax'`. [OWASP A07]
- `manage.py check` and `manage.py runserver` MUST pass with zero errors or warnings when `.env` is populated.

## Requirements
1. WHEN a developer creates and activates `.venv` (`python3 -m venv .venv && source .venv/bin/activate`) and runs `pip install -r requirements.txt`, THE SYSTEM SHALL install Django, `pymysql`, and `python-dotenv` with no errors.
2. WHEN `python manage.py check` is executed with `.env` populated, THE SYSTEM SHALL confirm system checks pass without errors.
3. WHEN a developer executes `python manage.py runserver`, THE SYSTEM SHALL bind to `http://127.0.0.1:8000/`.
4. WHEN an HTTP GET request is sent to `http://127.0.0.1:8000/`, THE SYSTEM SHALL respond with HTTP 200 and the smoke-test string `"Expense Tracker — up."`.
5. THE SYSTEM SHALL load environment variables from `.env` using `load_dotenv()` at the top of `expense_tracker/settings.py`.
6. THE SYSTEM SHALL configure `DATABASES['default']` in `settings.py` to use `django.db.backends.mysql` pointing to `127.0.0.1:3306` with credentials supplied by `.env`.
7. THE SYSTEM SHALL commit `.env.example` containing all required keys with empty values:
   `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.

## Failure Modes & Edge Cases
1. **Missing `.env` file:** WHEN `.env` does not exist, `settings.py` SHALL fall back to safe local development defaults (`DEBUG=True`, `DB_HOST=127.0.0.1`, `DB_PORT=3306`) or raise an informative `ImproperlyConfigured` exception for missing `SECRET_KEY`.
2. **MySQL Server Unreachable:** WHEN the local MySQL server is stopped and a database command is run, THE SYSTEM SHALL output an explicit connection refused error referencing port 3306 rather than a silent failure.
3. **Platform Activation Differences:** THE SYSTEM SHALL document both macOS/Linux (`source .venv/bin/activate`) and Windows (`.\.venv\Scripts\activate`) activation commands in setup notes.

## Acceptance Criteria
- [ ] Git repository initialized with `git status` clean and `.venv/` untracked.
- [ ] `pip install -r requirements.txt` succeeds cleanly in a fresh `.venv`.
- [ ] `python manage.py check` reports `System check identified no issues (0 silenced).`
- [ ] `curl -i http://127.0.0.1:8000/` returns HTTP 200 with text `"Expense Tracker — up."`.
- [ ] `git status` verifies `.env` is ignored and `.env.example` is tracked.

## Design

### Project Directory Layout
```
expense-tracker/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
├── expense_tracker/
│   ├── __init__.py          # pymysql.install_as_MySQLdb()
│   ├── settings.py          # MySQL config, dotenv, installed apps, cookie flags
│   ├── urls.py              # Root router
│   ├── wsgi.py
│   └── asgi.py
├── tracker/
│   ├── __init__.py
│   ├── apps.py              # TrackerConfig
│   ├── urls.py              # App routes (smoke-test, auth, dashboard)
│   ├── views.py             # View functions
│   └── models.py            # (stub in spec 01)
├── templates/               # Global templates directory
│   └── base.html            # (placeholder in spec 01)
└── static/
    ├── css/
    └── js/
```

### `expense_tracker/__init__.py`
```python
import pymysql

# Enable PyMySQL as the MySQLdb driver for Django on macOS/Windows
pymysql.install_as_MySQLdb()
```

### `expense_tracker/settings.py` (Excerpt)
```python
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key-change-in-production')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'tracker',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'expense_tracker'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}

# Cookie Hardening (OWASP A07)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'
```

### `.env.example`
```bash
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DB_NAME=expense_tracker
DB_USER=root
DB_PASSWORD=
DB_HOST=127.0.0.1
DB_PORT=3306
```

### `requirements.txt`
```
Django>=5.0,<5.2
pymysql>=1.1.0
python-dotenv>=1.0.0
```

## Current State
- `[verified]` Django Lecture 10 covers project structure (`django-admin startproject`, `startapp`, `urls.py`, `views.py`).
- `[verified]` MySQL Workbench is running locally on port 3306 on Sam's machine.
- `[assumed]` Group teammates have Python 3.10+ installed locally.

## Tests
- `test_system_checks_pass (R2)` — `python manage.py check` executes with returncode 0.
- `test_smoke_route_status_200 (R4)` — `GET /` returns status code 200 with expected text.
- `test_mysql_driver_installed (R1)` — `python -c "import pymysql; import MySQLdb"` succeeds without error.

## Constraints
- Dependencies: none (phase 01).
- Downstream: `02-database-schema`, `03-frontend-design-system`, `04-user-auth` build directly onto this layout.
