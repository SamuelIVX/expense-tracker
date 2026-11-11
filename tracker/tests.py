"""
Tests for tracker application infrastructure and smoke routes.
"""

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.conf import settings
import sys

class ScaffoldSmokeTests(SimpleTestCase):
    """Verifies baseline project scaffolding and smoke-test routing."""

    def test_smoke_route_status_200(self):
        """GET / returns HTTP 200 with expected smoke-test string."""
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Expense Tracker — up.")

    def test_mysql_driver_bridged(self):
        """Verifies pymysql is installed and registered as MySQLdb."""
        self.assertIn('MySQLdb', sys.modules)

    def test_security_settings(self):
        """Verifies required cookie and session security flags are enabled."""
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, 'Lax')
        self.assertIn('tracker', settings.INSTALLED_APPS)
