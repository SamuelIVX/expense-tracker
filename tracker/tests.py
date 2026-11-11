"""
Tests for tracker application infrastructure, models, and commands.
"""

from decimal import Decimal
from datetime import date
from pathlib import Path
from django.test import SimpleTestCase, TestCase, RequestFactory
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.models import User, AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.messages import SUCCESS, ERROR
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import ProtectedError
from django.db.utils import IntegrityError
from django.core.management import call_command
from unittest.mock import patch
import importlib
import sys
import pymysql
from expense_tracker import settings as app_settings
from .models import Category, Transaction

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

class CategoryModelTests(TestCase):
    """Verifies Category entity rules and constraints."""

    def test_create_category_with_defaults(self):
        """Category initializes with specified name and default hex color."""
        cat = Category.objects.create(name="Groceries")
        self.assertEqual(str(cat), "Groceries")
        self.assertEqual(cat.color, "#2D7DD2")

    def test_category_name_uniqueness(self):
        """Creating duplicate category names raises IntegrityError."""
        Category.objects.create(name="Utilities", color="#123456")
        with self.assertRaises(IntegrityError):
            Category.objects.create(name="Utilities", color="#654321")

class TransactionModelTests(TestCase):
    """Verifies Transaction entity rules, invariants, and cascades."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="securepassword123")
        self.category = Category.objects.create(name="Dining", color="#FF5733")

    def test_create_valid_transaction(self):
        """Transaction persists with valid decimal amount, date, and relations."""
        tx = Transaction.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal("25.50"),
            tx_date=date.today(),
            note="Lunch with team"
        )
        self.assertEqual(tx.amount, Decimal("25.50"))
        self.assertIn(f"Transaction #{tx.pk} - $25.50", str(tx))

    def test_amount_must_be_positive_on_validation(self):
        """Model validation fails if transaction amount is zero or negative."""
        tx_zero = Transaction(
            user=self.user,
            category=self.category,
            amount=Decimal("0.00"),
            tx_date=date.today()
        )
        with self.assertRaises(ValidationError):
            tx_zero.full_clean()

        tx_neg = Transaction(
            user=self.user,
            category=self.category,
            amount=Decimal("-10.00"),
            tx_date=date.today()
        )
        with self.assertRaises(ValidationError):
            tx_neg.full_clean()

    def test_amount_database_check_constraint(self):
        """Database check constraint chk_amount_pos rejects zero, negative, and out-of-bounds values on create."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Transaction.objects.create(
                    user=self.user,
                    category=self.category,
                    amount=Decimal("0.00"),
                    tx_date=date.today()
                )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Transaction.objects.create(
                    user=self.user,
                    category=self.category,
                    amount=Decimal("-5.00"),
                    tx_date=date.today()
                )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Transaction.objects.create(
                    user=self.user,
                    category=self.category,
                    amount=Decimal("1000000.00"),
                    tx_date=date.today()
                )

    def test_amount_max_value_boundary(self):
        """Transaction amount exceeding max limit fails validation."""
        tx_huge = Transaction(
            user=self.user,
            category=self.category,
            amount=Decimal("1000000.00"),
            tx_date=date.today()
        )
        with self.assertRaises(ValidationError):
            tx_huge.full_clean()

    def test_cascade_delete_on_user_removal(self):
        """Deleting a user removes all their associated transactions."""
        Transaction.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal("15.00"),
            tx_date=date.today()
        )
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 1)
        self.user.delete()
        self.assertEqual(Transaction.objects.count(), 0)

    def test_protect_delete_on_category_removal(self):
        """Deleting a category with existing transactions is blocked by ProtectedError."""
        Transaction.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal("15.00"),
            tx_date=date.today()
        )
        with self.assertRaises(ProtectedError):
            self.category.delete()

class SeedCategoriesCommandTests(TestCase):
    """Verifies the seed_categories management command."""

    def test_seed_categories_idempotent(self):
        """Running seed_categories seeds initial 7 categories and avoids duplicate entries."""
        call_command('seed_categories')
        count_after_first = Category.objects.count()
        self.assertEqual(count_after_first, 7)

        # Verify correct category attributes and colors
        food = Category.objects.get(name='Food')
        self.assertEqual(food.color, '#FF5733')

        expected_names = {"Food", "Transport", "Housing", "Entertainment", "Health", "Shopping", "Other"}
        actual_names = set(Category.objects.values_list('name', flat=True))
        self.assertEqual(actual_names, expected_names)

        # Run again to verify idempotency
        call_command('seed_categories')
        count_after_second = Category.objects.count()
        self.assertEqual(count_after_first, count_after_second)

class FrontendDesignSystemTests(TestCase):
    """Verifies Spec 03 Frontend Design System: base template, tokens, accessibility, and nav states."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="alex", password="password123")

    def test_base_template_unauthenticated_nav(self):
        """Anonymous visitor sees branding, Login, and Register links; no authenticated nav items."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        rendered = render_to_string('base.html', {'user': request.user}, request=request)

        self.assertIn('ExpenseTracker', rendered)
        self.assertIn(f'href="{reverse("login")}"', rendered)
        self.assertIn(f'href="{reverse("register")}"', rendered)
        self.assertNotIn(f'href="{reverse("dashboard")}"', rendered)
        self.assertNotIn(f'action="{reverse("logout")}"', rendered)

    def test_base_template_authenticated_nav(self):
        """Authenticated user sees Dashboard, Add Expense, History, and Logout with username."""
        request = self.factory.get('/')
        request.user = self.user
        rendered = render_to_string('base.html', {'user': request.user}, request=request)

        self.assertIn('ExpenseTracker', rendered)
        self.assertIn(f'href="{reverse("dashboard")}"', rendered)
        self.assertIn(f'href="{reverse("add_transaction")}"', rendered)
        self.assertIn(f'href="{reverse("transaction_history")}"', rendered)
        self.assertIn(f'action="{reverse("logout")}"', rendered)
        self.assertIn('Logout (alex)', rendered)
        self.assertNotIn(f'href="{reverse("login")}"', rendered)
        self.assertNotIn(f'href="{reverse("register")}"', rendered)

    def test_base_template_accessibility_landmarks(self):
        """Template renders required semantic landmarks and accessibility controls."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        rendered = render_to_string('base.html', {'user': request.user}, request=request)

        # WCAG landmarks and controls
        self.assertIn('class="et-skip-link"', rendered)
        self.assertIn('href="#main-content"', rendered)
        self.assertIn('<header class="et-header" role="banner">', rendered)
        self.assertIn('<main id="main-content" class="et-main et-container" tabindex="-1">', rendered)
        self.assertIn('<footer class="et-footer" role="contentinfo">', rendered)
        self.assertIn('aria-label="Main Navigation"', rendered)
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1.0">', rendered)
        self.assertIn('CSC 226 — Web Database Applications', rendered)

    def test_django_messages_live_announcement(self):
        """Messages framework renders alerts with role='status' for info/success and role='alert' for errors."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        setattr(request, 'session', {})
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        messages.add(SUCCESS, "Transaction created successfully.")
        messages.add(ERROR, "Could not save transaction.")

        rendered = render_to_string('base.html', {'messages': messages, 'user': request.user}, request=request)

        self.assertIn('et-alert--success', rendered)
        self.assertIn('role="status"', rendered)
        self.assertIn('Transaction created successfully.', rendered)
        self.assertIn('et-alert--error', rendered)
        self.assertIn('role="alert"', rendered)
        self.assertIn('Could not save transaction.', rendered)

    def test_static_css_and_js_exist(self):
        """Static style.css and ui.js files resolve cleanly through Django static finders."""
        css_found = finders.find('css/style.css')
        js_found = finders.find('js/ui.js')

        self.assertIsNotNone(css_found)
        self.assertIsNotNone(js_found)
        self.assertTrue(Path(css_found).is_file())
        self.assertTrue(Path(js_found).is_file())

    def test_logout_post_clears_session(self):
        """POST /logout/ terminates user session and redirects to login."""
        self.client.force_login(self.user)
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))

        # Verify session is flushed and user is unauthenticated
        response_check = self.client.get(reverse('index'))
        self.assertFalse(response_check.wsgi_request.user.is_authenticated)

    def test_scaffold_routes_reach_distinct_endpoints(self):
        """Verifies each advertised scaffold route resolves with proper auth protection."""
        protected_routes = ['dashboard', 'add_transaction', 'transaction_history']
        public_routes = ['login', 'register']

        # Unauthenticated: protected routes redirect to login
        for route_name in protected_routes:
            url = reverse(route_name)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('login'), response.url)

        # Authenticated: protected routes return HTTP 200
        self.client.force_login(self.user)
        for route_name in protected_routes:
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200)

        # Public routes return HTTP 200
        for route_name in public_routes:
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200)
