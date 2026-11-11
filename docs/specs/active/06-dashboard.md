# Spec: Dashboard

## Applicable Skills
- `owasp-security`: A05 Injection defense (strict parameterization with `%s`), DB-API `%` escaping (`%%Y-%%m`), row-level multi-tenant isolation.
- `better-accessibility`: ARIA progress bar semantics (`role="progressbar"`, `aria-valuenow`, `aria-valuetext`), accessible heading hierarchy.
- `better-ui`: Data display cards, optical typographic hierarchy, semantic color coding for budgets.

## Objective
Build the application centerpiece: an analytical spending dashboard displaying the current month's
total expenditure, a per-category spending breakdown, and an accessible budget progress indicator.
To directly satisfy the **"MySQL Queries" and "MySQL interfacing with Python"** criteria in the CSC 226
syllabus, the aggregate calculations are executed using **hand-written, parameterized raw SQL queries**
via `django.db.connection.cursor()` rather than abstracted ORM methods.

## Scope
- Package: `expense-tracker`
- Modifies (creates):
  - `templates/tracker/dashboard.html` (dashboard template with summary cards, progress bar, and breakdown table)
- Modifies (existing):
  - `tracker/views.py` (adds `dashboard_view` executing raw SQL aggregations)
  - `tracker/urls.py` (registers `/dashboard/` as the default post-login landing route)
- Off-limits: `tracker/models.py` (02); `style.css` (03); auth routes (04).

## Non-Goals
- No custom user budget configuration UI in v1 (default budget is fixed at $500.00/month).
- No historical multi-month comparison navigation (always focuses on current calendar month).
- No Chart.js graph (reserved for optional `08-stretch-chart`).

## Invariants
- ALL SQL queries MUST be parameterized with `%s` and passed a parameters list — zero string formatting or f-strings in queries. [OWASP A05 / ASVS 1.2.4]
- When using PyMySQL/DB-API cursor execution, literal `%` signs in SQL functions (e.g. `DATE_FORMAT(..., '%%Y-%%m')`) MUST be escaped as double `%%` to prevent Python string format collisions. [DB-API Invariant]
- ALL queries MUST filter by `user_id = %s` using `request.user.id` — users MUST NEVER be able to see another user's financial totals. [OWASP A01 / Data Isolation]
- Empty result sets MUST return `0.00` via `COALESCE(SUM(amount), 0)`, never `None` or an unhandled null pointer.
- The budget progress bar element MUST implement complete ARIA attributes: `role="progressbar"`, `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"`, and `aria-valuetext`. [WCAG 4.1.2]

## Requirements
1. THE SYSTEM SHALL query the database using raw SQL to calculate the current month's total spending:
   ```sql
   SELECT COALESCE(SUM(amount), 0) AS total
   FROM tracker_transaction
   WHERE user_id = %s
     AND DATE_FORMAT(tx_date, '%%Y-%%m') = %s
   ```
2. THE SYSTEM SHALL query the database using raw SQL with a `JOIN` and `GROUP BY` to calculate the category breakdown for the current month:
   ```sql
   SELECT c.name, c.color, COALESCE(SUM(t.amount), 0) AS total
   FROM tracker_transaction t
   JOIN tracker_category c ON t.category_id = c.id
   WHERE t.user_id = %s
     AND DATE_FORMAT(t.tx_date, '%%Y-%%m') = %s
   GROUP BY c.id, c.name, c.color
   ORDER BY total DESC
   ```
3. THE SYSTEM SHALL compute the budget utilization against a $500.00 monthly baseline:
   - `budget_percent = min(round((monthly_total / 500.0) * 100, 1), 100)`
4. WHEN `monthly_total` == 0, THE SYSTEM SHALL display a clear zero-state banner: `"No expenses recorded for this month yet. Record your first expense!"` with a button link to `/add/`.
5. WHEN `monthly_total` > 0, THE SYSTEM SHALL render:
   - Monthly summary card with current month name and formatted total spend (`$XX.XX`)
   - The accessible `.et-progress` budget bar:
     - Default blue bar when spend < 80% ($400)
     - Warning amber bar (`.et-progress__bar--warn`) when 80% ≤ spend < 100%
     - Danger red bar (`.et-progress__bar--danger`) when spend ≥ 100% ($500)
   - Category breakdown table displaying category badge (with `color`), total amount, and percentage of monthly total.
6. THE SYSTEM SHALL pass `category_breakdown` to the template as a clean list of dictionaries: `[{'name': str, 'color': str, 'total': float, 'percent': float}]`.

## Failure Modes & Edge Cases
1. **No Transactions in System:** WHEN a new user logs in with zero transactions, queries execute cleanly and return `0.00` total without throwing division-by-zero errors.
2. **Month Boundary:** Transactions dated in adjacent months (e.g., last day of previous month) MUST be strictly excluded by the `DATE_FORMAT` filter.
3. **Database Disconnection:** Any operational database exception SHALL fail closed and display an error page rather than exposing SQL syntax to the client.

## Acceptance Criteria
- [ ] Navigating to `/dashboard/` executes raw SQL via `connection.cursor()` with literal `%` escaped as `%%`.
- [ ] Adding an expense of $100 updates the dashboard total to $100.00 immediately.
- [ ] Progress bar element includes valid `role="progressbar"` and `aria-valuenow`.
- [ ] At $420 spend, the progress bar turns amber (`.et-progress__bar--warn`).
- [ ] At $510 spend, the progress bar turns red (`.et-progress__bar--danger`) and displays a budget warning.
- [ ] Creating transactions under User B does not alter User A's dashboard figures.

## Design

### `tracker/views.py` (Dashboard Implementation)
```python
from datetime import date
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db import connection

@login_required
def dashboard_view(request):
    user_id = request.user.id
    today = date.today()
    current_month_str = today.strftime('%Y-%m')     # '2026-11'
    current_month_name = today.strftime('%B %Y')    # 'November 2026'
    monthly_budget = 500.00

    with connection.cursor() as cursor:
        # 1. Total monthly spend (Raw SQL with literal % escaped as %%)
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM tracker_transaction
            WHERE user_id = %s
              AND DATE_FORMAT(tx_date, '%%%%Y-%%%%m') = %s
        """, [user_id, current_month_str])
        row = cursor.fetchone()
        monthly_total = float(row[0]) if row else 0.0

        # 2. Per-category spend breakdown (Raw SQL with JOIN + GROUP BY)
        cursor.execute("""
            SELECT c.name, c.color, COALESCE(SUM(t.amount), 0) AS total
            FROM tracker_transaction t
            JOIN tracker_category c ON t.category_id = c.id
            WHERE t.user_id = %s
              AND DATE_FORMAT(t.tx_date, '%%%%Y-%%%%m') = %s
            GROUP BY c.id, c.name, c.color
            ORDER BY total DESC
        """, [user_id, current_month_str])
        category_rows = cursor.fetchall()

    category_breakdown = []
    for name, color, total in category_rows:
        total_float = float(total)
        percent = round((total_float / monthly_total * 100), 1) if monthly_total > 0 else 0.0
        category_breakdown.append({
            'name': name,
            'color': color,
            'total': total_float,
            'percent': percent,
        })

    budget_percent = min(round((monthly_total / monthly_budget) * 100, 1), 100.0)
    is_budget_warn = 80.0 <= budget_percent < 100.0
    is_budget_exceeded = monthly_total >= monthly_budget

    context = {
        'month_name': current_month_name,
        'monthly_total': monthly_total,
        'monthly_budget': monthly_budget,
        'budget_percent': budget_percent,
        'is_budget_warn': is_budget_warn,
        'is_budget_exceeded': is_budget_exceeded,
        'category_breakdown': category_breakdown,
    }
    return render(request, 'tracker/dashboard.html', context)
```

### `templates/tracker/dashboard.html` (Accessible Progress Bar Excerpt)
```html
{% extends "base.html" %}

{% block title %}Dashboard &bull; {{ month_name }}{% endblock %}

{% block content %}
<div class="et-dashboard">
    <div class="et-dashboard__header">
        <h1>Spending Dashboard</h1>
        <p class="et-subtitle">{{ month_name }}</p>
    </div>

    <!-- Budget & Summary Card -->
    <div class="et-card et-summary-card">
        <div class="et-summary-metric">
            <span class="et-metric-label">Spent This Month</span>
            <span class="et-metric-value">${{ monthly_total|floatformat:2 }}</span>
            <span class="et-metric-budget">Monthly Budget: ${{ monthly_budget|floatformat:2 }}</span>
        </div>

        <div class="et-progress-wrapper">
            <div class="et-progress"
                 role="progressbar"
                 aria-valuenow="{{ budget_percent }}"
                 aria-valuemin="0"
                 aria-valuemax="100"
                 aria-valuetext="{{ budget_percent }}% of ${{ monthly_budget|floatformat:0 }} monthly budget">
                <div class="et-progress__bar {% if is_budget_exceeded %}et-progress__bar--danger{% elif is_budget_warn %}et-progress__bar--warn{% endif %}"
                     style="width: {{ budget_percent }}%;">
                </div>
            </div>
            <div class="et-progress-meta">
                <span>{{ budget_percent }}% of monthly budget</span>
                {% if is_budget_exceeded %}
                    <strong class="et-text-danger">Budget exceeded!</strong>
                {% elif is_budget_warn %}
                    <strong class="et-text-warn">Approaching budget limit (≥80%)</strong>
                {% endif %}
            </div>
        </div>
    </div>

    <!-- Category Breakdown Section -->
    <div class="et-card">
        <div class="et-card__header">
            <h2>Spending by Category</h2>
            <a href="{% url 'add_transaction' %}" class="et-btn et-btn--sm et-btn--primary">+ Add Expense</a>
        </div>

        {% if category_breakdown %}
            <table class="et-table">
                <thead>
                    <tr>
                        <th scope="col">Category</th>
                        <th scope="col" class="et-text-right">Total Spent</th>
                        <th scope="col" class="et-text-right">Share</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in category_breakdown %}
                        <tr>
                            <td>
                                <span class="et-badge" style="background-color: {{ item.color }};" aria-hidden="true"></span>
                                {{ item.name }}
                            </td>
                            <td class="et-text-right">${{ item.total|floatformat:2 }}</td>
                            <td class="et-text-right">{{ item.percent }}%</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% else %}
            <div class="et-zero-state">
                <p>No expenses recorded for {{ month_name }}.</p>
                <a href="{% url 'add_transaction' %}" class="et-btn et-btn--primary">Record First Expense</a>
            </div>
        {% endif %}
    </div>
</div>
{% endblock %}
```

## Current State
- `[verified]` The CSC 226 syllabus specifically emphasizes "MySQL Queries", "MySQL interfacing with Python", and aggregate operations.

## Tests
- `test_dashboard_raw_sql_execution` — verifies `connection.cursor()` query executes with valid user parameters.
- `test_dashboard_zero_state` — user with no transactions receives 0.00 total and zero-state template.
- `test_dashboard_budget_alert_thresholds` — verifies warning and danger flags trigger at 80% and 100%.

## Constraints
- Dependencies: `02-database-schema`, `03-frontend-design-system`, `04-user-auth`, `05-add-transaction`.
- Downstream: `08-stretch-chart` consumes `category_breakdown` from this view.
