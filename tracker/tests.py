"""
Tests for tracker application infrastructure and smoke routes.
"""

from django.test import SimpleTestCase
from django.urls import reverse
from django.conf import settings
from unittest.mock import patch
import importlib
import sys
import pymysql
from expense_tracker import settings as app_settings

class ScaffoldSmokeTests(SimpleTestCase):
    """Verifies baseline project scaffolding and smoke-test routing."""

    def test_smoke_route_status_200(self):
        """GET / returns HTTP 200 with expected smoke-test string."""
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Expense Tracker — up.")

    def test_mysql_driver_bridged(self):
        """Verifies pymysql is directly registered as the MySQLdb module object."""
        self.assertIs(sys.modules.get('MySQLdb'), pymysql)

    def test_security_settings(self):
        """Verifies baseline cookie and session security flags are enabled."""
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, 'Lax')
        self.assertIn('tracker', settings.INSTALLED_APPS)

    def test_cookie_security_policy_matrix(self):
        """Verifies secure-cookie flags evaluate correctly across DEBUG modes."""
        self.addCleanup(importlib.reload, app_settings)

        # Production mode: DEBUG is False -> Cookies must be secure
        with patch.dict('os.environ', {'DEBUG': 'False', 'SECRET_KEY': 'test-prod-secret-key'}):
            importlib.reload(app_settings)
            self.assertTrue(app_settings.SESSION_COOKIE_SECURE)
            self.assertTrue(app_settings.CSRF_COOKIE_SECURE)
            self.assertFalse(app_settings.DEBUG)

        # Development mode: DEBUG is True -> Cookies allow plain HTTP on localhost
        with patch.dict('os.environ', {'DEBUG': 'True', 'SECRET_KEY': 'test-dev-secret-key'}):
            importlib.reload(app_settings)
            self.assertFalse(app_settings.SESSION_COOKIE_SECURE)
            self.assertFalse(app_settings.CSRF_COOKIE_SECURE)
            self.assertTrue(app_settings.DEBUG)
