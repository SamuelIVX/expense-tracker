# Spec: User Authentication

## Applicable Skills
- `owasp-security`: A07 Authentication Failures, A01 Broken Access Control, PBKDF2 hashing, open redirect prevention on `next`, non-enumerating error messages.
- `better-writing`: Non-punitive, clear feedback copy; distinct calls-to-action ("Create Account", "Log In").

## Objective
Implement secure user registration, login, and logout by configuring Django's built-in authentication
subsystem (`django.contrib.auth`). Store passwords as salted PBKDF2-SHA256 hashes, maintain server-side
sessions via Django's secure signed session cookies, enforce CSRF protection, prevent open redirects on
login, and provide the `@login_required` decorator to protect all application data routes. This spec
satisfies the Web Application Security and User Authentication requirements in the CSC 226 syllabus.

## Scope
- Package: `expense-tracker`
- Modifies (creates):
  - `tracker/forms.py` (custom `RegisterForm` extending `django.contrib.auth.forms.UserCreationForm`)
  - `templates/registration/login.html` (login form matching design tokens)
  - `templates/registration/register.html` (registration form matching design tokens)
- Modifies (existing):
  - `tracker/views.py` (adds `register_view` and configures `LoginView`/`LogoutView`)
  - `tracker/urls.py` (registers `/register/`, `/login/`, `/logout/`)
- Off-limits: `tracker/models.py` (owned by `02-database-schema`); CSS tokens (owned by `03-frontend-design-system`).

## Non-Goals
- No OAuth / social login (GitHub, Google) — coursework scope focuses on username/password auth.
- No email verification or password reset flows in v1.
- No two-factor authentication (2FA).

## Invariants
- Passwords MUST be hashed using Django's default PBKDF2 with a SHA256 hash — plaintext storage is strictly forbidden. [OWASP A02 / ASVS 6.2.1]
- All auth POST forms MUST include `{% csrf_token %}` to prevent Cross-Site Request Forgery. [OWASP A01]
- Every mutative auth request (login, register, logout) MUST use HTTP POST — GET-based logout is forbidden. [Security Best Practice]
- Authenticated users navigating to `/login/` or `/register/` MUST be redirected to `/dashboard/`.
- The `next` query parameter on login MUST be validated against `url_has_allowed_host_and_scheme` to prevent Open Redirect vulnerabilities. [OWASP A01]
- Error messages on failed login attempts MUST be generic ("Invalid username or password") to prevent user enumeration. [OWASP A07]

## Requirements
1. WHEN an unauthenticated user GETs `/register/`, THE SYSTEM SHALL render the registration form with fields: `username`, `password`, and `confirm_password`.
2. WHEN a user POSTs valid registration data, THE SYSTEM SHALL create a new `User` record in `auth_user`, log the user into the session automatically, and redirect to `/dashboard/` with a success message `"Welcome to Expense Tracker!"`.
3. WHEN a user attempts to register with an already existing username (case-insensitive), THE SYSTEM SHALL reject the submission and display `"A user with that username already exists."`.
4. WHEN an unauthenticated user GETs `/login/`, THE SYSTEM SHALL render the login form with fields: `username` and `password`.
5. WHEN valid credentials are submitted via POST to `/login/`, THE SYSTEM SHALL authenticate the user, create an authenticated session, and redirect to the validated `next` query parameter or `/dashboard/`.
6. WHEN invalid credentials are submitted to `/login/`, THE SYSTEM SHALL re-render the login page with a non-enumerating error message `"Invalid username or password."`.
7. WHEN a user POSTs to `/logout/`, THE SYSTEM SHALL terminate the session, flush session cookies, and redirect to `/login/` with a message `"You have been logged out."`.
8. THE SYSTEM SHALL protect all transaction and dashboard views using Django's `@login_required` decorator.

## Failure Modes & Edge Cases
1. **Open Redirect Attack:** WHEN an external attacker supplies `?next=https://evil.com`, Django's `LoginView` SHALL sanitize the target using `url_has_allowed_host_and_scheme` and safely redirect to `/dashboard/`.
2. **Weak Passwords:** THE SYSTEM SHALL validate passwords against standard complexity rules (minimum 8 characters, not entirely numeric) via `UserCreationForm`.
3. **Session Expiration:** Expired sessions navigating to a protected route SHALL smoothly redirect to `/login/?next=<path>` with an informational message.

## Acceptance Criteria
- [ ] Navigating to `/dashboard/` while logged out redirects to `/login/?next=/dashboard/`.
- [ ] Submitting a new valid user on `/register/` creates a row in MySQL's `auth_user` table.
- [ ] Inspecting `auth_user.password` in MySQL Workbench confirms it begins with `pbkdf2_sha256$` (never plaintext).
- [ ] Submitting bad credentials on `/login/` shows an error and does not log the user in.
- [ ] Attempting an external redirect (`?next=//malicious.com`) redirects safely to `/dashboard/`.
- [ ] Logging out successfully invalidates the session.

## Design

### `tracker/forms.py`
```python
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class RegisterForm(UserCreationForm):
    username = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'et-input',
            'placeholder': 'Choose a username',
            'autofocus': True,
            'autocomplete': 'username',
        })
    )

    class Meta:
        model = User
        fields = ('username',)

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username
```

### `tracker/views.py` (Auth Additions)
```python
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from .forms import RegisterForm

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to Expense Tracker, {user.username}!")
            return redirect('dashboard')
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {'form': form})
```

## Current State
- `[verified]` Django's `django.contrib.auth` provides built-in views, session middleware, and PBKDF2 hashing.
- `[verified]` The CSC 226 syllabus specifically grades user authentication and web application security.

## Tests
- `test_unauthenticated_redirect` — unauthenticated GET `/dashboard/` redirects to `/login/`.
- `test_registration_hashes_password` — newly registered user's `password` in DB starts with `pbkdf2_sha256$`.
- `test_open_redirect_prevented` — passing `?next=http://evil.com` to login redirects to `/dashboard/`.
- `test_duplicate_username_rejected` — duplicate username attempt renders form error.

## Constraints
- Dependencies: `01-project-scaffold`, `02-database-schema`, and `03-frontend-design-system` must merge first.
- Downstream: `05-add-transaction`, `06-dashboard`, and `07-transaction-history` require the authenticated `request.user`.
