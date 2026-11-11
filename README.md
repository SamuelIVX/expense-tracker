# Expense Tracker

A web database application for logging and reviewing daily personal spending. Authenticated users
can record transactions by amount, category, note, and date; browse and filter their history; and
see a live spending dashboard that breaks down how much they've spent this month by category. The
project is coursework for CSC 226 — Web Database Applications (Fall 2026) and is graded on
database design (20%), user interface craftsmanship (10%), and full-stack integration / security / auth (20%).

Stack: Python 3 + Django 5 (backend), MySQL (local database via MySQL Workbench), vanilla HTML + CSS + JavaScript (Django templates).
Group size: 2–3. No heavy frontend framework (React/Vue/Tailwind off-limits). Chart.js via CDN as stretch only.

---

## Domain Glossary

| Term | Definition |
|---|---|
| **User** | An authenticated account managed via `django.contrib.auth.models.User`; owns all their own transactions. |
| **Category** | A named spending bucket (Food, Transport, Housing, etc.) with a display color. Seeded at deploy time. |
| **Transaction** | One recorded expense: an amount (`DECIMAL(10,2)`), a category FK, an optional note, and a transaction date. Belongs to exactly one User. |
| **Budget** | A monthly spending cap ($500 default in v1) compared against the current month's transaction totals on the dashboard. |
| **Dashboard** | The landing page after login (`/dashboard/`). Shows the current month's total spend, budget progress bar, and a per-category breakdown. |
| **History** | A filterable list of all a user's past transactions (`/history/`), newest first, with delete controls. |

---

## Skill Integration Matrix

To ensure industry-grade quality and strict rubric compliance, each spec binds to specialized domain skills:

| Skill | Focus Areas | Applied Specs |
|---|---|---|
| **`owasp-security`** | Password hashing (PBKDF2), SQL injection prevention (`%s` DB-API), IDOR prevention, CSRF tokens, session hardening, CDN Subresource Integrity (SRI). | `01`, `04`, `05`, `06`, `07`, `08` |
| **`better-accessibility`** | WCAG 2.2 AA compliance: `:focus-visible` outlines, `prefers-reduced-motion`, `role="progressbar"`, `aria-describedby` form errors, `scope="col"` table headers, row-specific `aria-label`s. | `03`, `05`, `06`, `07` |
| **`better-ui`** | Semantic CSS custom properties (tokens), layout spacing, loading button states, progress bar transitions. | `03`, `06` |
| **`better-writing`** | Non-punitive, clear, actionable interface copy; descriptive button labels; empty state guidance. | `03`, `04`, `05`, `06`, `07`, `09` |
| **`codebase-design`** | Normalized 3NF schema, cascade constraints, composite indexing (`idx_tx_user_date`), clean contract seams. | `01`, `02`, `06` |

---

## Specs (Dependency Order)

| # | Spec | Who | Applicable Skills | One-Line Summary |
|---|------|-----|-------------------|-----------------|
| 01 | [`docs/specs/active/01-project-scaffold.md`](docs/specs/active/01-project-scaffold.md) | You | `owasp-security`, `codebase-design` | Git repo init, venv, Django skeleton, `.env`, `.gitignore`, MySQL `pymysql` driver setup. |
| 02 | [`docs/specs/active/02-database-schema.md`](docs/specs/active/02-database-schema.md) | You | `codebase-design` | MySQL DDL (`schema.sql`) for Workbench + Django Models (`Category`, `Transaction`) + seed data. |
| 03 | [`docs/specs/active/03-frontend-design-system.md`](docs/specs/active/03-frontend-design-system.md) | Teammates | `better-accessibility`, `better-ui`, `better-writing` | CSS design tokens (`style.css`), base Django template (`base.html`), UI transitions, loading states. |
| 04 | [`docs/specs/active/04-user-auth.md`](docs/specs/active/04-user-auth.md) | You | `owasp-security`, `better-writing` | Django built-in auth (`LoginView`, `LogoutView`), registration form, `@login_required` enforcement. |
| 05 | [`docs/specs/active/05-add-transaction.md`](docs/specs/active/05-add-transaction.md) | Teammate | `better-accessibility`, `owasp-security`, `better-writing` | Add expense form with client/server validation, CSRF tokens, and user ownership assignment. |
| 06 | [`docs/specs/active/06-dashboard.md`](docs/specs/active/06-dashboard.md) | You | `owasp-security`, `better-accessibility`, `better-ui` | Current month aggregation via raw parameterized SQL (`SUM`, `GROUP BY`, `JOIN`) + budget progress bar. |
| 07 | [`docs/specs/active/07-transaction-history.md`](docs/specs/active/07-transaction-history.md) | Teammate | `owasp-security`, `better-accessibility`, `better-writing` | Filterable transaction table (by category and month), ownership-verified DELETE. |
| 08 | [`docs/specs/active/08-stretch-chart.md`](docs/specs/active/08-stretch-chart.md) | Anyone | `owasp-security`, `better-ui` | Optional Chart.js CDN bar chart with SRI on the dashboard breakdown. |
| 09 | [`docs/specs/active/09-submission.md`](docs/specs/active/09-submission.md) | You | `better-writing` | Final submission README, rubric checklist, `WALKTHROUGH.md`, and demo video script. |

---

## Dependency Graph

```
01 project scaffold
        │
        ▼
02 database schema
        │
        ├──────────────────────────┐
        ▼                          ▼
03 frontend design system    04 user auth
        │                          │
        └────────────┬─────────────┘
                     ▼
              05 add transaction
                     │
                     ▼
              06 dashboard
                     │
                     ▼
              07 transaction history
                     │
              08 stretch chart (optional, branches from 06)
                     │
                     ▼
              09 submission
```

---

## Cross-Spec Seams & Interface Registry

| Shared Contract / Type / File | Canonical Owner Spec | Consumer Specs | Contract Stability |
|---|---|---|---|
| `expense_tracker/settings.py` | `01-project-scaffold` | `02`, `03`, `04` | Database connection, installed apps, static/template paths, security flags; frozen after 04 |
| `schema.sql` (Workbench DDL) | `02-database-schema` | `09` (submission) | Normalized tables (`categories`, `transactions`), FKs, seed data; frozen after 02 |
| `tracker/models.py` (`Category`, `Transaction`) | `02-database-schema` | `05`, `06`, `07` | Core data models; frozen after 02 |
| `templates/base.html` | `03-frontend-design-system` | `04`, `05`, `06`, `07`, `08` | Base Jinja/Django layout, navbar, CSRF boilerplate, messages; frozen after 03 |
| `static/css/style.css` | `03-frontend-design-system` | `04..08` | Design tokens (`--et-*`), component styles, progress bar, accessibility rules; frozen after 03 |
| `static/js/ui.js` | `03-frontend-design-system` | `05`, `07` | Form submission spinner, button disable, toast dismissal |
| `tracker/urls.py` | `01-project-scaffold` | `04`, `05`, `06`, `07` | App URL registry; 01 creates, subsequent specs append endpoints |
| `@login_required` & user session | `04-user-auth` | `05`, `06`, `07` | Request user contract (`request.user.id`, `request.user.is_authenticated`) |
| `category_breakdown` data shape | `06-dashboard` | `08-stretch-chart` | List of dicts `[{'name': str, 'total': float, 'color': str}]` passed to template and JSON serializer |

---

## Time Estimates

| Spec | Estimate |
|---|---|
| 01 project scaffold | ~1.5 hr |
| 02 database schema | ~1.5 hr |
| 03 frontend design system | ~2 hr |
| 04 user auth | ~1.5 hr (simplified by Django `contrib.auth`) |
| 05 add transaction | ~2 hr |
| 06 dashboard | ~2 hr |
| 07 transaction history | ~2 hr |
| 08 stretch chart | ~1 hr (optional) |
| 09 submission | ~1 hr |

**Total:** ~14–15 hrs across the group (~5–7 hrs per person in a 2–3 person group).

---

## Definition of Done

- The app runs locally with `python manage.py runserver` inside an activated `.venv` with `.env` populated.
- Connected to local MySQL instance (`127.0.0.1:3306`) using `pymysql`.
- `schema.sql` executes cleanly in MySQL Workbench without errors.
- A new user can register, log in, and log out; unauthenticated access to protected routes redirects to `/login/`.
- Passwords stored as PBKDF2 hashes (Django default) — never plaintext.
- A logged-in user can add a transaction (amount, category, date, optional note) and see it immediately in `/history/`.
- The dashboard shows the current month's total spend and category breakdown calculated using **raw parameterized SQL queries** (`connection.cursor()`) to prove database query skills.
- The dashboard includes an accessible budget progress bar (`role="progressbar"`, green < 80%, amber ≥ 80%, red ≥ 100%).
- Transaction history is filterable by category and month (`?category=...&month=YYYY-MM`).
- A user can delete only their own transactions; foreign deletion attempts return HTTP 404 or 403.
- All SQL uses parameterized queries (`%s` with params list) with escaped date format strings (`%%Y-%%m`) — zero string concatenation.
- All forms enforce client-side validation and server-side validation with CSRF tokens (`{% csrf_token %}`).
- Secrets (`SECRET_KEY`, DB password) live in `.env` and are strictly git-ignored.

---

## Coursework Scope & Rubric Alignment (CSC 226)

This project is tailored specifically to Professor Joseph Tooker's grading distribution:

1. **Database Design (20%):**
   - Normalized 3NF tables (`categories`, `transactions`) with correct constraints and foreign keys (`ON DELETE CASCADE`).
   - Strict `DECIMAL(10, 2)` monetary representation.
   - Dual-presence: `schema.sql` for MySQL Workbench demonstration and Django `models.py` for application integration.
2. **User Interface Design / Idea (10%):**
   - Clean, purposeful CSS token system (no messy frameworks, no AI slop).
   - WCAG 2.2 AA accessible focus indicators and contrast ratios.
   - Client-side validation attributes (`required`, `min`, `step`) on all inputs.
   - Visual feedback: button submit loading spinner, CSS transition effects, and a dynamic budget progress bar.
3. **The Rest of the Work — Backend, Integration, Security (20%):**
   - Django 5 MVT architecture connecting to local MySQL.
   - Built-in session authentication (`django.contrib.auth`).
   - Web Application Security: Parameterized SQL queries (ASVS 1.2.4 / OWASP A05), strict row-level ownership isolation (OWASP A01), and CSRF token protection on all mutative requests.
