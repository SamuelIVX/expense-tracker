# Personal Expense Tracker

[![Build & Test](https://github.com/SamuelIVX/expense-tracker/actions/workflows/build.yml/badge.svg)](https://github.com/SamuelIVX/expense-tracker/actions/workflows/build.yml)
[![Course](https://img.shields.io/badge/Course-CSC%20226%20Web%20Database%20Applications-blue)](https://www.csi.cuny.edu/)
[![Python](https://img.shields.io/badge/Python-3.14-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2-green.svg)](https://www.djangoproject.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-orange.svg)](https://www.mysql.com/)
[![Tests](https://img.shields.io/badge/Tests-61%20Passing-brightgreen.svg)](tracker/tests.py)

A secure, database-driven web application for tracking and analyzing personal daily expenditures. Built for **CSC 226: Web Database Applications** (Fall 2026), this application allows authenticated users to log expenses, monitor monthly spending targets with a dynamic budget progress bar, visualize category breakdowns using an interactive Chart.js bar chart, and filter past transaction history.

The application demonstrates proficiency in **Relational Database Design**, **User Interface Craftsmanship**, and **Full-Stack Integration, Security & Authentication**.

---

## Table of Contents
- [Tech Stack & Architecture](#tech-stack--architecture)
- [Core Technical Pillars](#core-technical-pillars)
- [Feature Checklist](#feature-checklist)
- [Database Schema (3NF)](#database-schema-3nf)
- [Setup & Installation Guide](#setup--installation-guide)
- [Running Automated Tests](#running-automated-tests)

---

## Tech Stack & Architecture

- **Backend:** Python 3.14 + Django 5.2 (Model-View-Template architecture, session-based authentication, CSRF middleware).
- **Database:** MySQL 8.0 (InnoDB engine, 3NF schema, foreign key cascades/restrictions, decimal quantization, composite indexing). Connected to Django using `pymysql`.
- **Frontend:** Semantic HTML5, Vanilla CSS3 Custom Properties (Design Tokens), and Vanilla JavaScript (loading states, double-submit guard, alert dismissal). *Zero heavy frontend frameworks (React/Vue/Tailwind) per project requirements.*
- **Data Visualization (Stretch):** Chart.js 4.4.2 imported via CDN with Subresource Integrity (`integrity="sha256-..."`), offline guards, and safe JSON script embedding.
- **Testing & Tooling:** Pytest, `pytest-django`, GitHub Actions CI.

```
┌─────────────────────────────────────────────────────────────┐
│                       Client Browser                        │
│  - Semantic HTML5 & CSS Custom Properties Tokens            │
│  - Vanilla JavaScript (Double-submit guard, loading state)  │
│  - Chart.js 4.4.2 via CDN (Subresource Integrity Verified)  │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / HTTPS (Session Cookie & CSRF)
┌──────────────────────────────▼──────────────────────────────┐
│                    Django 5.2 Application                   │
│  - MVT Architecture (Views, Forms, Templates)               │
│  - Built-in Session Auth & PBKDF2 Password Hashing          │
│  - Strict Row-Level Data Isolation (request.user.id)        │
└──────────────────────────────┬──────────────────────────────┘
                               │ Parameterized SQL Queries (DB-API %s)
┌──────────────────────────────▼──────────────────────────────┐
│                       MySQL 8.0 Database                    │
│  - 3NF Normalized Schema (`schema.sql`)                     │
│  - Foreign Keys: `fk_tx_user` (CASCADE), `fk_tx_cat` (RESTRICT)
│  - Check Constraint: `chk_amount_pos` ($0.01 - $999,999.99) │
│  - Performance Index: `idx_tx_user_date (user_id, tx_date)`  │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Technical Pillars

The project is engineered around three foundational pillars:

### 1. Database Design
- **3NF Relational Normalization:** Complete separation of entity domains (`auth_user`, `tracker_category`, `tracker_transaction`), eliminating insertion, update, and deletion anomalies.
- **Referential Integrity & Cascades:**
  - `fk_tx_user`: References `auth_user(id)` (`INT`) with `ON DELETE CASCADE` in `schema.sql` and `on_delete=models.CASCADE` in Django ORM (deleting a user account cleans up all associated transactions).
  - `fk_tx_category`: References `tracker_category(id)` with `ON DELETE RESTRICT` in `schema.sql` and `on_delete=models.PROTECT` in Django ORM (prevents deletion of categories currently referenced by active transactions).
- **Domain Constraints & Monetary Types:**
  - `DECIMAL(10, 2)` monetary columns throughout—guaranteeing exact cent precision and eliminating floating-point rounding errors.
  - Database check constraint `chk_amount_pos` (`amount > 0.00 AND amount <= 999999.99`).
- **Query Optimization Indexing:** Composite index `idx_tx_user_date (user_id, tx_date)` supporting high-performance date-window filtering and dashboard aggregation queries.
- **Deliverables:** Raw MySQL DDL in [`schema.sql`](schema.sql) (executable in MySQL Workbench) mirroring Django ORM models in [`tracker/models.py`](tracker/models.py).

### 2. User Interface Design & Craftsmanship
- **Design Tokens System:** Centralized CSS custom properties in [`static/css/style.css`](static/css/style.css) defining brand colors, typography, spacing, surface elevations, and responsive breakpoints.
- **Accessibility (WCAG 2.2 AA Compliance):**
  - High-contrast color palette meeting WCAG 2.2 AA (≥ 4.5:1 text-on-background ratio; distinct :focus-visible outlines on interactive controls).
  - Visible `:focus-visible` outlines on all interactive elements.
  - Screen reader support: `role="progressbar"`, `aria-valuenow`, `aria-describedby` form error bindings, and table column scopes (`scope="col"`).
  - Respects `prefers-reduced-motion` media queries.
- **Responsive Layout:** Adaptive desktop and mobile layouts (`.et-stat-grid`, `.et-grid`, `.et-table-responsive`).
- **Interactive Feedback:** Dynamic submit button loading spinner (`static/js/ui.js`), double-submit prevention, and smooth alert toast dismissal.
- **Dynamic Budget Pacing Indicator:** Visual progress bar that dynamically shifts color based on spending thresholds:
  - Normal Blue (< 70% of budget)
  - Amber Warning (70% – 89.9% of budget)
  - Red Danger (≥ 90% of budget)
- **Interactive Chart Visualization (Stretch):** Chart.js horizontal bar chart paired with an accessible data table (`aria-describedby="categoryBreakdownTable"` and internal screen-reader alternative).

### 3. Full-Stack Integration, Security & Auth
- **Django 5.2 MVT Architecture:** Clean separation of concerns between models, views, and templates.
- **Parameterized Raw SQL Query Engine:** To prove direct database query proficiency, all dashboard aggregations, monthly summaries, and history filters in [`tracker/queries.py`](tracker/queries.py) are executed via `connection.cursor()` with `%s` DB-API parameterization—strictly immune to SQL injection (OWASP A03).
- **Authentication & Password Security:**
  - User registration and login utilizing Django's authentication system.
  - Passwords hashed using industry-standard **PBKDF2 with SHA-256** and 870,000 hashing iterations (OWASP A02).
  - Unauthenticated access to protected views (`/dashboard/`, `/add/`, `/history/`) strictly blocked via `@login_required` decorators with safe return redirects (`?next=`).
- **Row-Level Authorization (IDOR Defense):** Every database query and transaction mutation explicitly scopes to `user_id = request.user.id`. Transaction deletion requires HTTP POST and verifies record ownership; attempts to access or delete another user's records return HTTP 404/403 (OWASP A01).
- **CSRF & Form Hardening:** All forms require valid CSRF middleware tokens (`{% csrf_token %}`).
- **Subresource Integrity (SRI):** CDN-loaded Chart.js bundle verified via cryptographic SHA-256 hash (`integrity` and `crossorigin="anonymous"` attributes per OWASP A08).

---

## Feature Checklist

- [x] **Project Scaffold & Tooling (Spec 01):** Django 5 project structure, virtual environment, `.env` configuration, MySQL `pymysql` driver bridge, Pytest test runner.
- [x] **Database Schema & DDL (Spec 02):** Normalized 3NF MySQL schema, `schema.sql`, Django models, range check constraints, category seed command (`seed_categories`).
- [x] **Frontend Design System (Spec 03):** Semantic CSS tokens, WCAG 2.2 AA accessible base layout, loading spinner, double-submit guard.
- [x] **User Authentication (Spec 04):** Registration, login, logout, PBKDF2 password hashing, `@login_required` route protection.
- [x] **Add Expense Transaction (Spec 05):** Validated expense entry form, accessible error bindings, user ownership assignment.
- [x] **Dashboard Metrics & Raw SQL (Spec 06):** Parameterized raw SQL aggregation queries, monthly total spending, category breakdown, dynamic budget progress bar.
- [x] **Transaction History & Filtering (Spec 07):** Filterable history table (by category, month, and note search), 15-item pagination, safe POST-only transaction deletion.
- [x] **Spending Breakdown Chart (Spec 08 - Stretch):** Interactive horizontal bar chart via CDN with Subresource Integrity (SRI) and accessible dual-table presentation.
- [x] **Project Documentation (Spec 09):** Comprehensive `README.md` detailing architecture, setup, testing, and security.

---

## Database Schema (3NF)

```sql
-- Category Lookup Table
CREATE TABLE tracker_category (
    id    BIGINT       AUTO_INCREMENT PRIMARY KEY,
    name  VARCHAR(50)  NOT NULL UNIQUE,
    color VARCHAR(7)   NOT NULL DEFAULT '#2D7DD2'
) ENGINE=InnoDB;

-- Transaction Table
CREATE TABLE tracker_transaction (
    id          BIGINT         AUTO_INCREMENT PRIMARY KEY,
    user_id     INT            NOT NULL,
    category_id BIGINT         NOT NULL,
    amount      DECIMAL(10, 2) NOT NULL,
    note        VARCHAR(255)   NULL,
    tx_date     DATE           NOT NULL,
    created_at  DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_tx_user_date (user_id, tx_date),
    CONSTRAINT fk_tx_user     FOREIGN KEY (user_id)     REFERENCES auth_user(id)        ON DELETE CASCADE,
    CONSTRAINT fk_tx_category FOREIGN KEY (category_id) REFERENCES tracker_category(id) ON DELETE RESTRICT,
    CONSTRAINT chk_amount_pos CHECK (amount > 0.00 AND amount <= 999999.99)
) ENGINE=InnoDB;
```

---

## Setup & Installation Guide

Follow these steps to set up and run the application locally from a clean clone:

### Prerequisites
- Python 3.10+ (tested on Python 3.14)
- MySQL Server 8.0.16+ running locally (enforced CHECK constraints support; tested via MySQL Workbench)
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/SamuelIVX/expense-tracker.git
cd expense-tracker
```

### 2. Create and Activate Virtual Environment
```bash
# macOS / Linux (bash/zsh):
python3 -m venv .venv
source .venv/bin/activate

# Windows (Command Prompt):
.\.venv\Scripts\activate.bat

# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your local MySQL credentials:
```bash
# macOS / Linux / PowerShell:
cp .env.example .env

# Windows (Command Prompt):
copy .env.example .env
```
Edit `.env`:
```ini
DEBUG=True
SECRET_KEY=your-secure-development-secret-key-here
DB_NAME=expense_tracker
DB_USER=root
DB_PASSWORD=YourMySQLPasswordHere
DB_HOST=127.0.0.1
DB_PORT=3306
```

### 5. Initialize the MySQL Database
Create the database in MySQL:
```bash
# Option A: Command Line (using MySQL client)
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS expense_tracker CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Option B: MySQL Workbench
# Execute: CREATE DATABASE IF NOT EXISTS expense_tracker CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 6. Run Migrations & Seed Default Categories
```bash
# Apply Django authentication and application migrations to create tables
python manage.py migrate

# Seed standard spending categories (Food, Transport, Housing, etc.)
python manage.py seed_categories
```

> **Note on `schema.sql`:** [`schema.sql`](schema.sql) contains the standalone MySQL 8.0 DDL reference script illustrating the 3NF schema, check constraints, and composite indexes for inspection in MySQL Workbench.

### 7. Start the Local Server
```bash
python manage.py runserver
```
Navigate to `http://127.0.0.1:8000/login/` or `http://127.0.0.1:8000/register/` in your browser to create an account and begin tracking expenses.

---

## Running Automated Tests

The project includes 61 comprehensive automated test cases covering models, forms, parameterized queries, authentication isolation, view routing, accessibility attributes, and XSS prevention.

Tests can be executed across all platforms (macOS, Linux, and Windows) against both the fast in-memory SQLite runner and the live MySQL instance:

### 1. In-Memory SQLite Suite (Fast / No DB Setup Required)
```bash
# macOS / Linux (bash/zsh):
DB_ENGINE=sqlite python -m pytest --ds=expense_tracker.test_settings

# Windows (Command Prompt):
set DB_ENGINE=sqlite && python -m pytest --ds=expense_tracker.test_settings

# Windows (PowerShell):
$env:DB_ENGINE="sqlite"; python -m pytest --ds=expense_tracker.test_settings
```

### 2. Local MySQL 8.0 Suite (Exercises Live Database)
```bash
# macOS / Linux (bash/zsh):
DB_ENGINE=mysql python -m pytest --ds=expense_tracker.settings

# Windows (Command Prompt):
set DB_ENGINE=mysql && python -m pytest --ds=expense_tracker.settings

# Windows (PowerShell):
$env:DB_ENGINE="mysql"; python -m pytest --ds=expense_tracker.settings
```

All 61 tests pass cleanly on both backends.
