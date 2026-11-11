"""
Tests for tracker application infrastructure, models, and commands.
"""

from decimal import Decimal
from datetime import date
from pathlib import Path
from django.utils import timezone
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
from urllib.parse import quote
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
        self.assertRedirects(response, reverse('login'), fetch_redirect_response=False)

        # Verify session is flushed and user is unauthenticated
        response_check = self.client.get(reverse('index'))
        self.assertFalse(response_check.wsgi_request.user.is_authenticated)

    def test_scaffold_routes_reach_distinct_endpoints(self):
        """Verifies each advertised scaffold route resolves with proper auth protection."""
        protected_routes = ['dashboard', 'add_transaction', 'transaction_history']
        public_routes = ['login', 'register']

        # Unauthenticated: protected routes redirect to login with next parameter
        for route_name in protected_routes:
            url = reverse(route_name)
            response = self.client.get(url)
            self.assertRedirects(
                response,
                f"{reverse('login')}?next={url}",
                fetch_redirect_response=False,
            )

        # Authenticated: protected routes return HTTP 200
        self.client.force_login(self.user)
        for route_name in protected_routes:
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200)

        # Public routes: when logged out, return HTTP 200
        self.client.logout()
        for route_name in public_routes:
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200)

class UserAuthenticationTests(TestCase):
    """Verifies Spec 04 User Authentication: registration, login, logout, security invariants, and redirects."""

    def setUp(self):
        self.username = "testuser"
        self.password = "ValidPass123!"
        self.user = User.objects.create_user(username=self.username, password=self.password)

    def test_registration_creates_user_and_hashes_password(self):
        """Valid registration creates user with PBKDF2 hash, signs them in, and redirects to dashboard."""
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
        })
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

        new_user = User.objects.get(username='newuser')
        self.assertTrue(new_user.password.startswith('pbkdf2_sha256$'))
        self.assertNotEqual(new_user.password, 'ComplexPass123!')

        # Verify authenticated session
        response_check = self.client.get(reverse('index'))
        self.assertEqual(response_check.wsgi_request.user, new_user)

    def test_registration_duplicate_username_case_insensitive(self):
        """Registration rejects duplicate usernames regardless of casing."""
        response = self.client.post(reverse('register'), {
            'username': 'TestUser',  # existing user is 'testuser'
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A user with that username already exists.")
        self.assertEqual(User.objects.filter(username__iexact='testuser').count(), 1)

    def test_registration_password_mismatch(self):
        """Registration rejects mismatched passwords."""
        response = self.client.post(reverse('register'), {
            'username': 'differentuser',
            'password1': 'ComplexPass123!',
            'password2': 'MismatchedPass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        form = response.context['form']
        self.assertIn('password2', form.errors)
        self.assertFalse(User.objects.filter(username='differentuser').exists())

    def test_registration_integrity_error_handled(self):
        """Concurrent duplicate registration caught by db IntegrityError adds form error."""
        from tracker.forms import RegisterForm
        with patch.object(RegisterForm, 'save', side_effect=IntegrityError("Duplicate entry")):
            response = self.client.post(reverse('register'), {
                'username': 'uniqueuser',
                'password1': 'ComplexPass123!',
                'password2': 'ComplexPass123!',
            })
            self.assertEqual(response.status_code, 200)
            self.assertIn('form', response.context)
            form = response.context['form']
            self.assertIn('username', form.errors)
            self.assertIn("A user with that username already exists.", form.errors['username'])
            self.assertFalse(User.objects.filter(username='uniqueuser').exists())

    def test_login_valid_credentials(self):
        """Valid login creates session and redirects to dashboard."""
        response = self.client.post(reverse('login'), {
            'username': self.username,
            'password': self.password,
        })
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

        response_check = self.client.get(reverse('index'))
        self.assertEqual(response_check.wsgi_request.user, self.user)

    def test_login_invalid_credentials_non_enumerating(self):
        """Invalid credentials show non-enumerating error and user remains unauthenticated."""
        response = self.client.post(reverse('login'), {
            'username': self.username,
            'password': 'WrongPassword123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct username and password")

        response_check = self.client.get(reverse('index'))
        self.assertFalse(response_check.wsgi_request.user.is_authenticated)

    def test_login_open_redirect_prevented(self):
        """Supplying an untrusted external URL in ?next safely redirects to dashboard while safe relative URLs work."""
        # Positive control: safe relative redirect succeeds
        safe_url = reverse('transaction_history')
        response_safe = self.client.post(f"{reverse('login')}?next={quote(safe_url)}", {
            'username': self.username,
            'password': self.password,
        })
        self.assertRedirects(response_safe, safe_url, fetch_redirect_response=False)
        self.client.logout()

        # Negative control: untrusted external schemes/hosts redirect to default dashboard
        evil_targets = ['https://evil.com', '//evil.com', 'http://attacker.org/steal']
        for evil_url in evil_targets:
            for query_val in (evil_url, quote(evil_url)):
                response = self.client.post(f"{reverse('login')}?next={query_val}", {
                    'username': self.username,
                    'password': self.password,
                })
                self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)
                self.client.logout()

    def test_authenticated_user_redirected_from_auth_pages(self):
        """Logged-in users visiting login or register are redirected to dashboard."""
        self.client.force_login(self.user)
        for route_name in ['login', 'register']:
            response = self.client.get(reverse(route_name))
            self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

class AddTransactionViewTests(TestCase):
    """Verifies Spec 05 Add Transaction form, validation, security binding, and view handling."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="ValidPass123!")
        self.other_user = User.objects.create_user(username="otheruser", password="ValidPass123!")
        self.category = Category.objects.create(name="Groceries", color="#2ECC71")

    def test_unauthenticated_user_redirected_to_login(self):
        """Anonymous access to GET or POST /add/ redirects to login with next parameter."""
        add_url = reverse('add_transaction')
        for method in ['get', 'post']:
            client_fn = getattr(self.client, method)
            response = client_fn(add_url)
            self.assertRedirects(response, f"{reverse('login')}?next={add_url}", fetch_redirect_response=False)

    def test_get_add_transaction_renders_form_with_defaults(self):
        """Logged-in user sees add transaction form with today's date and available categories."""
        fixed_today = date(2026, 11, 10)
        with patch('django.utils.timezone.localdate', return_value=fixed_today):
            self.client.force_login(self.user)
            response = self.client.get(reverse('add_transaction'))
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, 'tracker/add_transaction.html')
            self.assertContains(response, "Add New Expense")
            self.assertContains(response, f'value="{fixed_today.isoformat()}"')
            self.assertContains(response, "Groceries")

    def test_post_valid_transaction_creates_record_for_user(self):
        """Valid submission persists transaction belonging to the logged-in user and redirects."""
        self.client.force_login(self.user)
        today = timezone.localdate()
        response = self.client.post(reverse('add_transaction'), {
            'category': self.category.id,
            'amount': '45.50',
            'tx_date': today.isoformat(),
            'note': 'Trader Joe run',
        }, follow=True)
        self.assertRedirects(response, reverse('transaction_history'))
        self.assertContains(response, "Added expense: $45.50 for Groceries.")
        self.assertTemplateUsed(response, 'tracker/history.html')

        self.assertEqual(Transaction.objects.count(), 1)
        tx = Transaction.objects.first()
        self.assertEqual(tx.user, self.user)
        self.assertEqual(tx.category, self.category)
        self.assertEqual(tx.amount, Decimal('45.50'))
        self.assertEqual(tx.note, 'Trader Joe run')
        self.assertEqual(tx.tx_date, today)

    def test_post_transaction_cannot_spoof_different_user(self):
        """Submitting another user_id does not assign the transaction to that user."""
        self.client.force_login(self.user)
        today = timezone.localdate()
        response = self.client.post(reverse('add_transaction'), {
            'category': self.category.id,
            'amount': '20.00',
            'tx_date': today.isoformat(),
            'note': 'Spoof attempt',
            'user': self.other_user.id,
            'user_id': self.other_user.id,
        })
        self.assertRedirects(response, reverse('transaction_history'), fetch_redirect_response=False)

        tx = Transaction.objects.first()
        self.assertEqual(tx.user, self.user)
        self.assertNotEqual(tx.user, self.other_user)

    def test_post_invalid_amount_rejected(self):
        """Zero, negative, overflow, and excessive precision amounts are rejected by validation."""
        self.client.force_login(self.user)
        today = timezone.localdate()
        for invalid_amount in ['0.00', '-15.50', '0', '1000000.00', '10.001']:
            response = self.client.post(reverse('add_transaction'), {
                'category': self.category.id,
                'amount': invalid_amount,
                'tx_date': today.isoformat(),
            })
            self.assertEqual(response.status_code, 200)
            self.assertIn('form', response.context)
            self.assertIn('amount', response.context['form'].errors)
            self.assertEqual(Transaction.objects.count(), 0)

    def test_post_invalid_category_rejected(self):
        """Invalid category ID fails validation and does not save transaction."""
        self.client.force_login(self.user)
        today = timezone.localdate()
        response = self.client.post(reverse('add_transaction'), {
            'category': 99999,
            'amount': '30.00',
            'tx_date': today.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('category', response.context['form'].errors)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_post_whitespace_note_normalized_to_none(self):
        """Whitespace-only notes are normalized to None."""
        self.client.force_login(self.user)
        today = timezone.localdate()
        response = self.client.post(reverse('add_transaction'), {
            'category': self.category.id,
            'amount': '12.00',
            'tx_date': today.isoformat(),
            'note': '   ',
        })
        self.assertRedirects(response, reverse('transaction_history'), fetch_redirect_response=False)
        tx = Transaction.objects.first()
        self.assertIsNone(tx.note)

    def test_post_invalid_form_renders_accessible_aria_attributes(self):
        """Invalid fields are marked with aria-invalid='true' and linked to error element ids."""
        self.client.force_login(self.user)
        response = self.client.post(reverse('add_transaction'), {
            'amount': '-5.00',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'aria-describedby="id_amount-error"')
        self.assertContains(response, 'id="id_amount-error"')
