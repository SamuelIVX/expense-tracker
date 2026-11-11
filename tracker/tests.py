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
import json
import re
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

class DashboardViewTests(TestCase):
    """Verifies Spec 06 Dashboard: raw SQL aggregation, budget progress bar, isolation, and limits."""

    def setUp(self):
        self.user = User.objects.create_user(username="dashuser", password="ValidPass123!")
        self.other_user = User.objects.create_user(username="otherdashuser", password="ValidPass123!")
        self.cat_food = Category.objects.create(name="Food", color="#FF5733")
        self.cat_transport = Category.objects.create(name="Transport", color="#33A8FF")

    def test_unauthenticated_user_redirected_to_login(self):
        """Anonymous access to /dashboard/ redirects to login with next parameter."""
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}", fetch_redirect_response=False)

    def test_dashboard_empty_state_for_new_user(self):
        """New user with no transactions sees zero totals, 0% budget used, and empty state prompts."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tracker/dashboard.html')
        self.assertEqual(response.context['total_spent'], Decimal('0'))
        self.assertEqual(response.context['tx_count'], 0)
        self.assertEqual(response.context['budget_percentage'], 0.0)
        self.assertContains(response, "$0.00")
        self.assertContains(response, "No spending recorded")
        self.assertContains(response, "No transactions recorded yet")

    def test_dashboard_aggregates_current_month_spending(self):
        """Transactions in current month are aggregated by raw SQL into totals and category shares."""
        today = timezone.localdate()
        Transaction.objects.create(user=self.user, category=self.cat_food, amount=Decimal('150.00'), tx_date=today)
        Transaction.objects.create(user=self.user, category=self.cat_transport, amount=Decimal('50.00'), tx_date=today)

        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['total_spent'], Decimal('200.00'))
        self.assertEqual(response.context['tx_count'], 2)
        self.assertEqual(response.context['budget_percentage'], 20.0)
        self.assertEqual(response.context['budget_remaining'], Decimal('800.00'))

        breakdown = response.context['category_breakdown']
        self.assertEqual(len(breakdown), 2)
        # Food should be first (150.00 > 50.00)
        self.assertEqual(breakdown[0]['name'], "Food")
        self.assertEqual(breakdown[0]['total'], Decimal('150.00'))
        self.assertEqual(breakdown[0]['percentage'], 75.0)

        self.assertEqual(breakdown[1]['name'], "Transport")
        self.assertEqual(breakdown[1]['total'], Decimal('50.00'))
        self.assertEqual(breakdown[1]['percentage'], 25.0)

    def test_dashboard_excludes_other_months(self):
        """Transactions from previous or future months do not affect current month analytics."""
        import calendar
        today = timezone.localdate()
        start_of_month = today.replace(day=1)
        _, last_day = calendar.monthrange(today.year, today.month)
        end_of_month = today.replace(day=last_day)

        # Boundary transactions inside current month (inclusive start and end)
        Transaction.objects.create(user=self.user, category=self.cat_food, amount=Decimal('25.00'), tx_date=start_of_month)
        Transaction.objects.create(user=self.user, category=self.cat_food, amount=Decimal('50.00'), tx_date=end_of_month)

        # Transactions outside month boundary
        # Day before start of month
        prev_date = date(today.year - 1 if today.month == 1 else today.year, 12 if today.month == 1 else today.month - 1, 28)
        Transaction.objects.create(user=self.user, category=self.cat_food, amount=Decimal('500.00'), tx_date=prev_date)
        # First day of next month
        next_date = date(today.year + 1 if today.month == 12 else today.year, 1 if today.month == 12 else today.month + 1, 1)
        Transaction.objects.create(user=self.user, category=self.cat_food, amount=Decimal('300.00'), tx_date=next_date)

        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['total_spent'], Decimal('75.00'))
        self.assertEqual(response.context['tx_count'], 2)

    def test_dashboard_isolates_user_data(self):
        """Spending from other users is strictly excluded from the dashboard metrics."""
        today = timezone.localdate()
        Transaction.objects.create(user=self.other_user, category=self.cat_food, amount=Decimal('999.00'), tx_date=today)

        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['total_spent'], Decimal('0'))
        self.assertEqual(response.context['tx_count'], 0)
        self.assertEqual(len(response.context['category_breakdown']), 0)
        self.assertEqual(len(response.context['recent_transactions']), 0)

    def test_dashboard_budget_progress_thresholds_and_clamping(self):
        """Progress bar applies warning at >=70%, danger at >=90%, and clamps width at 100%."""
        today = timezone.localdate()
        self.client.force_login(self.user)

        # Baseline < 70%
        tx = Transaction.objects.create(user=self.user, category=self.cat_food, amount=Decimal('500.00'), tx_date=today)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['progress_class'], "")
        self.assertEqual(response.context['progress_width'], 50.0)

        # Warning >= 70%
        tx.amount = Decimal('750.00')
        tx.save()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['progress_class'], "et-progress__bar--warn")
        self.assertEqual(response.context['progress_width'], 75.0)

        # Danger >= 90%
        tx.amount = Decimal('920.00')
        tx.save()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['progress_class'], "et-progress__bar--danger")
        self.assertEqual(response.context['progress_width'], 92.0)

        # Over budget (> 100%): clamped at 100% width
        tx.amount = Decimal('1250.00')
        tx.save()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['progress_class'], "et-progress__bar--danger")
        self.assertEqual(response.context['progress_width'], 100.0)
        self.assertTrue(response.context['is_over_budget'])
        self.assertEqual(response.context['over_budget_amount'], Decimal('250.00'))
        self.assertContains(response, 'role="progressbar"')
        self.assertContains(response, 'aria-valuenow="100.0"')

    def test_dashboard_recent_transactions_capped_at_five_and_ordered(self):
        """Dashboard lists at most 5 recent transactions ordered descending by date and id."""
        today = timezone.localdate()
        for i in range(1, 8):
            Transaction.objects.create(
                user=self.user,
                category=self.cat_food,
                amount=Decimal(f'{i * 10}.00'),
                tx_date=today,
                note=f"Tx #{i}"
            )

        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        recent = response.context['recent_transactions']
        self.assertEqual(len(recent), 5)
        self.assertEqual(recent[0]['note'], "Tx #7")
        self.assertEqual(recent[4]['note'], "Tx #3")

class DashboardChartTests(TestCase):
    """Verifies Spec 08 Stretch Feature: Spending Breakdown Chart (Chart.js via CDN with SRI)."""

    def setUp(self):
        self.user = User.objects.create_user(username="chartuser", password="ValidPass123!")
        self.other_user = User.objects.create_user(username="otherchartuser", password="ValidPass123!")
        self.cat_food = Category.objects.create(name="Food", color="#FF5733")
        self.cat_transport = Category.objects.create(name="Transport", color="#33A8FF")
        self.cat_entertainment = Category.objects.create(name="Entertainment", color="#A233FF")

    def test_chart_canvas_and_cdn_rendered_when_expenses_exist(self):
        """When spending exists in the current month, canvas and CDN script with SRI are rendered."""
        today = timezone.localdate()
        Transaction.objects.create(
            user=self.user,
            category=self.cat_food,
            amount=Decimal('120.50'),
            tx_date=today,
            note="Groceries"
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        # Context JSON payload verification
        self.assertIn('category_breakdown_data', response.context)
        self.assertIn('category_breakdown_json', response.context)
        self.assertEqual(len(response.context['category_breakdown_data']), 1)
        data = json.loads(response.context['category_breakdown_json'])
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], "Food")
        self.assertEqual(data[0]['color'], "#FF5733")
        self.assertEqual(data[0]['total'], 120.50)
        self.assertEqual(data[0]['percentage'], 100.0)

        # HTML canvas, accessible description, and CDN SRI verification
        self.assertContains(response, '<table class="et-table" id="categoryBreakdownTable">')
        self.assertContains(response, '<canvas id="categoryChart"')
        self.assertContains(response, 'role="img"')
        self.assertContains(response, 'aria-label="Horizontal bar chart showing spending by category"')
        self.assertContains(response, 'aria-describedby="categoryBreakdownTable"')
        self.assertContains(response, '<script id="category-breakdown-data" type="application/json">')
        self.assertContains(response, 'https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js')
        self.assertContains(response, 'integrity="sha256-')
        self.assertContains(response, 'crossorigin="anonymous"')
        self.assertContains(response, "if (typeof Chart === 'undefined') return;")
        self.assertContains(response, "new Chart(ctx,")

    def test_chart_canvas_and_cdn_not_rendered_when_zero_expenses(self):
        """When no expenses exist in the current month, chart canvas and CDN scripts are omitted."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        self.assertIn('category_breakdown_json', response.context)
        self.assertEqual(response.context['category_breakdown_json'], "[]")

        # Must not render canvas or load CDN script
        self.assertNotContains(response, '<canvas id="categoryChart"')
        self.assertNotContains(response, 'chart.umd.min.js')
        self.assertNotContains(response, "new Chart(ctx,")

    def test_chart_multi_category_aggregation_and_ordering(self):
        """Chart JSON encodes all categories ordered descending by spending with matching colors."""
        today = timezone.localdate()
        Transaction.objects.create(user=self.user, category=self.cat_transport, amount=Decimal('40.00'), tx_date=today)
        Transaction.objects.create(user=self.user, category=self.cat_food, amount=Decimal('160.00'), tx_date=today)
        Transaction.objects.create(user=self.user, category=self.cat_entertainment, amount=Decimal('80.00'), tx_date=today)

        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.context['category_breakdown_json'])
        self.assertEqual(len(data), 3)

        # Descending order: Food ($160) -> Entertainment ($80) -> Transport ($40)
        self.assertEqual(data[0]['name'], "Food")
        self.assertEqual(data[0]['total'], 160.00)
        self.assertEqual(data[0]['color'], "#FF5733")

        self.assertEqual(data[1]['name'], "Entertainment")
        self.assertEqual(data[1]['total'], 80.00)
        self.assertEqual(data[1]['color'], "#A233FF")

        self.assertEqual(data[2]['name'], "Transport")
        self.assertEqual(data[2]['total'], 40.00)
        self.assertEqual(data[2]['color'], "#33A8FF")

    def test_chart_user_data_isolation(self):
        """User only sees their own expenses in the chart breakdown payload."""
        today = timezone.localdate()
        # Other user has spending
        Transaction.objects.create(user=self.other_user, category=self.cat_food, amount=Decimal('500.00'), tx_date=today)

        # Current user has no spending
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['category_breakdown_json'], "[]")
        self.assertNotContains(response, '<canvas id="categoryChart"')

        # Current user adds their own expense
        Transaction.objects.create(user=self.user, category=self.cat_transport, amount=Decimal('25.00'), tx_date=today)
        response = self.client.get(reverse('dashboard'))
        data = json.loads(response.context['category_breakdown_json'])
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], "Transport")
        self.assertEqual(data[0]['total'], 25.00)

    def test_chart_xss_script_injection_escaped(self):
        """Category name with script injection is safely encoded without breaking HTML."""
        today = timezone.localdate()
        xss_cat = Category.objects.create(name="</script><script>alert('xss')</script>", color="#E74C3C")
        Transaction.objects.create(user=self.user, category=xss_cat, amount=Decimal('50.00'), tx_date=today)

        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        # Assert no raw unescaped script tag can break out of JSON data element
        content = response.content.decode('utf-8')
        self.assertNotIn("</script><script>alert('xss')</script>", content)
        self.assertIn('<script id="category-breakdown-data" type="application/json">', content)
        self.assertIn('\\u003C/script\\u003E', content)

        # Verify JSON parsed from the rendered DOM element matches expected data
        match = re.search(r'<script id="category-breakdown-data" type="application/json">(.*?)</script>', content)
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        self.assertEqual(data[0]['name'], "</script><script>alert('xss')</script>")
        self.assertEqual(data[0]['total'], 50.00)

class TransactionHistoryViewTests(TestCase):
    """Verifies Spec 07 Transaction History: filtering, searching, pagination, and safe deletion."""

    def setUp(self):
        self.user = User.objects.create_user(username="histuser", password="ValidPass123!")
        self.other_user = User.objects.create_user(username="otherhistuser", password="ValidPass123!")
        self.cat_food = Category.objects.create(name="Food", color="#FF5733")
        self.cat_transport = Category.objects.create(name="Transport", color="#33A8FF")

    def test_unauthenticated_user_redirected_to_login(self):
        """Anonymous access to history or delete endpoint redirects to login."""
        response = self.client.get(reverse('transaction_history'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('transaction_history')}", fetch_redirect_response=False)

        delete_url = reverse('delete_transaction', kwargs={'pk': 1})
        response_delete = self.client.post(delete_url)
        self.assertRedirects(response_delete, f"{reverse('login')}?next={delete_url}", fetch_redirect_response=False)

    def test_history_empty_state_for_user_with_no_records(self):
        """User with no transactions sees empty state without table."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('transaction_history'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tracker/history.html')
        self.assertEqual(response.context['filtered_count'], 0)
        self.assertEqual(response.context['filtered_total'], Decimal('0.00'))
        self.assertContains(response, "No transactions recorded yet")

    def test_history_isolates_user_data(self):
        """User sees only their own transactions and not other users' transactions."""
        today = timezone.localdate()
        tx_user = Transaction.objects.create(
            user=self.user, category=self.cat_food, amount=Decimal('42.00'), tx_date=today, note="My lunch"
        )
        tx_other = Transaction.objects.create(
            user=self.other_user, category=self.cat_food, amount=Decimal('99.00'), tx_date=today, note="Other lunch"
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('transaction_history'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['filtered_count'], 1)
        self.assertEqual(response.context['filtered_total'], Decimal('42.00'))
        self.assertContains(response, "My lunch")
        self.assertNotContains(response, "Other lunch")

    def test_history_filter_by_category(self):
        """Filtering by category returns only matching category records and recalculates total."""
        today = timezone.localdate()
        Transaction.objects.create(user=self.user, category=self.cat_food, amount=Decimal('25.00'), tx_date=today)
        Transaction.objects.create(user=self.user, category=self.cat_transport, amount=Decimal('15.00'), tx_date=today)

        self.client.force_login(self.user)
        response = self.client.get(f"{reverse('transaction_history')}?category={self.cat_food.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['filtered_count'], 1)
        self.assertEqual(response.context['filtered_total'], Decimal('25.00'))
        transactions = list(response.context['page_obj'])
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0]['category_name'], "Food")

    def test_history_filter_by_month(self):
        """Filtering by month returns only transactions inside that calendar month."""
        t1 = Transaction.objects.create(user=self.user, category=self.cat_food, amount=Decimal('30.00'), tx_date=date(2026, 11, 10))
        t2 = Transaction.objects.create(user=self.user, category=self.cat_food, amount=Decimal('40.00'), tx_date=date(2026, 10, 15))

        self.client.force_login(self.user)
        response = self.client.get(f"{reverse('transaction_history')}?month=2026-11")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['filtered_count'], 1)
        self.assertEqual(response.context['filtered_total'], Decimal('30.00'))
        transactions = list(response.context['page_obj'])
        self.assertEqual(transactions[0]['id'], t1.id)

    def test_history_filter_by_search_query(self):
        """Filtering by search string matches substrings inside the transaction note."""
        t1 = Transaction.objects.create(user=self.user, category=self.cat_food, amount=Decimal('10.00'), tx_date=date(2026, 11, 1), note="Whole Foods salad")
        t2 = Transaction.objects.create(user=self.user, category=self.cat_food, amount=Decimal('20.00'), tx_date=date(2026, 11, 2), note="Subway ticket")

        self.client.force_login(self.user)
        response = self.client.get(f"{reverse('transaction_history')}?q=foods")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['filtered_count'], 1)
        self.assertEqual(response.context['filtered_total'], Decimal('10.00'))
        self.assertContains(response, "Whole Foods salad")
        self.assertNotContains(response, "Subway ticket")

    def test_history_filter_by_search_query_escapes_like_wildcards(self):
        """Search query properly escapes LIKE wildcards like % to prevent broad matches."""
        Transaction.objects.create(
            user=self.user, category=self.cat_food, amount=Decimal('10.00'), tx_date=date(2026, 11, 1), note="50% off coupon"
        )
        Transaction.objects.create(
            user=self.user, category=self.cat_food, amount=Decimal('20.00'), tx_date=date(2026, 11, 2), note="500 dollars spent"
        )

        self.client.force_login(self.user)
        # Search specifically for term containing '%'
        response = self.client.get(f"{reverse('transaction_history')}?q=50%")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['filtered_count'], 1)
        self.assertEqual(response.context['filtered_total'], Decimal('10.00'))
        self.assertContains(response, "50% off coupon")
        self.assertNotContains(response, "500 dollars spent")

    def test_history_filter_by_non_ascii_digit_category_handled(self):
        """Passing non-ASCII digits like ² or invalid formats returns HTTP 200 without crashing."""
        Transaction.objects.create(user=self.user, category=self.cat_food, amount=Decimal('10.00'), tx_date=date(2026, 11, 1))

        self.client.force_login(self.user)
        for weird_param in ['²', '①', '99999999999999999999999999999999']:
            response = self.client.get(f"{reverse('transaction_history')}?category={quote(weird_param)}")
            self.assertEqual(response.status_code, 200)

    def test_history_pagination_and_query_preservation(self):
        """Pagination breaks lists into 15 items per page and preserves filter query params in links."""
        today = timezone.localdate()
        for i in range(1, 19):
            Transaction.objects.create(
                user=self.user,
                category=self.cat_food,
                amount=Decimal('10.00'),
                tx_date=today,
                note=f"Item {i}"
            )

        self.client.force_login(self.user)
        # Page 1
        response_p1 = self.client.get(f"{reverse('transaction_history')}?category={self.cat_food.id}")
        self.assertEqual(response_p1.status_code, 200)
        page1 = response_p1.context['page_obj']
        self.assertEqual(len(page1), 15)
        self.assertTrue(page1.has_next())
        self.assertEqual(response_p1.context['filtered_count'], 18)
        self.assertEqual(response_p1.context['filtered_total'], Decimal('180.00'))
        self.assertContains(response_p1, f'category={self.cat_food.id}')

        # Page 2
        response_p2 = self.client.get(f"{reverse('transaction_history')}?page=2&category={self.cat_food.id}")
        self.assertEqual(response_p2.status_code, 200)
        page2 = response_p2.context['page_obj']
        self.assertEqual(len(page2), 3)
        self.assertTrue(page2.has_previous())

    def test_delete_transaction_post_success(self):
        """POST to delete removes the record, flashes confirmation message, and redirects."""
        today = timezone.localdate()
        tx = Transaction.objects.create(
            user=self.user, category=self.cat_food, amount=Decimal('55.00'), tx_date=today, note="Dinner"
        )

        self.client.force_login(self.user)
        response = self.client.post(reverse('delete_transaction', kwargs={'pk': tx.id}), follow=True)
        self.assertRedirects(response, reverse('transaction_history'))
        self.assertFalse(Transaction.objects.filter(pk=tx.id).exists())
        self.assertContains(response, "Deleted expense of $55.00 for Food.")

    def test_delete_transaction_get_rejected_with_405(self):
        """GET request to delete endpoint is rejected with HTTP 405 Method Not Allowed."""
        today = timezone.localdate()
        tx = Transaction.objects.create(
            user=self.user, category=self.cat_food, amount=Decimal('55.00'), tx_date=today
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('delete_transaction', kwargs={'pk': tx.id}))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Transaction.objects.filter(pk=tx.id).exists())

    def test_delete_transaction_prevents_unauthorized_deletion_of_other_users(self):
        """Attempting to delete another user's transaction returns HTTP 404 without deleting."""
        today = timezone.localdate()
        other_tx = Transaction.objects.create(
            user=self.other_user, category=self.cat_food, amount=Decimal('88.00'), tx_date=today
        )

        self.client.force_login(self.user)
        response = self.client.post(reverse('delete_transaction', kwargs={'pk': other_tx.id}))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Transaction.objects.filter(pk=other_tx.id).exists())

    def test_delete_nonexistent_transaction_returns_404(self):
        """Attempting to delete a nonexistent transaction returns HTTP 404."""
        self.client.force_login(self.user)
        response = self.client.post(reverse('delete_transaction', kwargs={'pk': 99999}))
        self.assertEqual(response.status_code, 404)
