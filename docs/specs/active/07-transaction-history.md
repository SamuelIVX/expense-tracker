# Spec: Transaction History

## Applicable Skills
- `owasp-security`: A01 Broken Access Control (IDOR prevention on delete, scoped QuerySets), CSRF token enforcement.
- `better-accessibility`: Accessible data tables (`<th scope="col">`), row-specific action labels (`aria-label`), keyboard-accessible delete workflows.
- `better-writing`: Contextual empty states, plain language filter options ("All Categories", "Clear Filters").

## Objective
Build the transaction ledger page (`/history/`): a reverse-chronological, filterable table displaying
all expenses logged by the authenticated user, equipped with category and month filter controls and an
ownership-verified delete action per row. This spec demonstrates multi-criteria querying, relational
lookups, and secure mutation gating.

> **Ownership:** Beginner teammate. Route skeletons provided; teammate builds and styles the filter form, results table, and empty states.

## Scope
- Package: `expense-tracker`
- Modifies (creates):
  - `templates/tracker/history.html` (history ledger page with filter form and table)
- Modifies (existing):
  - `tracker/views.py` (adds `transaction_history_view` and `delete_transaction_view`)
  - `tracker/urls.py` (registers `/history/` and `/delete/<int:tx_id>/`)
- Off-limits: `schema.sql`, `tracker/models.py` (02); `style.css` (03); auth routes (04).

## Non-Goals
- No inline editing of past transactions in v1 (delete-and-recreate model).
- No export to CSV or PDF.
- No client-side infinite scroll or complex pagination (simple list view is sufficient for coursework scope).

## Invariants
- ALL queries MUST strictly scope to `user = request.user` — a user MUST NEVER view or delete another user's records. [OWASP A01 / Broken Access Control]
- The delete action MUST be executed via HTTP POST accompanied by a valid `{% csrf_token %}` — GET-based deletion links are strictly forbidden. [OWASP A01 / CSRF Prevention]
- An attempt to delete an ID that does not exist or belongs to another user MUST return HTTP 404, never silently succeed.
- Each delete button MUST provide an accessible name identifying the specific item (e.g. `aria-label="Delete Food expense of $45.50 on 2026-11-10"`). [Accessibility / WCAG 4.1.2]

## Requirements
1. WHEN an authenticated user GETs `/history/`, THE SYSTEM SHALL query their transactions ordered newest first (`-tx_date`, `-created_at`).
2. WHEN query parameter `category` is provided (e.g. `?category=Food`), THE SYSTEM SHALL filter results to transactions matching that category name.
3. WHEN query parameter `month` is provided in `YYYY-MM` format (e.g. `?month=2026-11`), THE SYSTEM SHALL filter results to transactions whose `tx_date` falls within that month.
4. WHEN both `category` and `month` parameters are provided, THE SYSTEM SHALL apply both criteria with logical AND.
5. THE SYSTEM SHALL render a filter toolbar containing:
   - Category dropdown `<select>` populated from `Category.objects.all()` plus an "All Categories" default option
   - Month picker (`<input type="month">`)
   - "Filter" submission button (GET form)
   - "Clear Filters" reset link
6. WHEN filters are active, THE SYSTEM SHALL pre-populate the filter inputs with the submitted values so the user sees their active query.
7. WHEN no transactions match the query, THE SYSTEM SHALL display a clear zero-state message `"No transactions match your criteria."` with a link to clear filters.
8. EACH table row MUST display:
   - Date (`YYYY-MM-DD`)
   - Category (with color badge)
   - Note (or "—" if blank)
   - Amount formatted in monospace (`$XX.XX`)
   - A `<form method="post" action="{% url 'delete_transaction' tx.id %}">` containing a CSRF token and a "Delete" button with a row-specific `aria-label`.
9. WHEN a POST is sent to `/delete/<tx_id>/`, THE SYSTEM SHALL verify that the transaction exists and `tx.user == request.user`, delete the record, set a flash message `"Expense deleted."`, and redirect back to `/history/`.

## Failure Modes & Edge Cases
1. **Malicious Delete Attempt (IDOR):** WHEN User A attempts to POST to `/delete/<User_B_tx_id>/`, `get_object_or_404(Transaction, id=tx_id, user=request.user)` SHALL immediately raise `Http404`.
2. **Invalid Month Format:** WHEN an invalid month string (e.g. `?month=invalid`) is passed in query params, THE SYSTEM SHALL ignore the month filter rather than crashing with an unhandled date parsing exception.

## Acceptance Criteria
- [ ] Navigating to `/history/` lists all transactions for the current user, newest first.
- [ ] Filtering by `Food` only shows food transactions.
- [ ] Filtering by month `2026-11` excludes transactions from other months.
- [ ] Each delete button has a unique `aria-label` readable by screen readers.
- [ ] Clicking "Delete" prompts confirmation and removes the row from MySQL.
- [ ] Attempting to delete another user's transaction ID via curl returns 404.

## Design

### `tracker/views.py` (History & Delete Implementation)
```python
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import Transaction, Category

@login_required
def transaction_history_view(request):
    transactions = Transaction.objects.filter(user=request.user).select_related('category')
    
    category_filter = request.GET.get('category', '').strip()
    month_filter = request.GET.get('month', '').strip()

    if category_filter and category_filter != 'all':
        transactions = transactions.filter(category__name=category_filter)

    if month_filter:
        try:
            parsed_date = datetime.strptime(month_filter, '%Y-%m')
            transactions = transactions.filter(
                tx_date__year=parsed_date.year,
                tx_date__month=parsed_date.month
            )
        except ValueError:
            pass  # Ignore malformed month param

    categories = Category.objects.all()

    context = {
        'transactions': transactions,
        'categories': categories,
        'selected_category': category_filter,
        'selected_month': month_filter,
    }
    return render(request, 'tracker/history.html', context)

@login_required
@require_POST
def delete_transaction_view(request, tx_id):
    # Enforces strict ownership check (OWASP A01)
    transaction = get_object_or_404(Transaction, id=tx_id, user=request.user)
    amount_str = f"${transaction.amount:.2f}"
    transaction.delete()
    messages.success(request, f"Expense of {amount_str} deleted.")
    return redirect('transaction_history')
```

### `templates/tracker/history.html`
```html
{% extends "base.html" %}

{% block title %}Transaction History &bull; Expense Tracker{% endblock %}

{% block content %}
<div class="et-card">
    <div class="et-card__header">
        <h1>Transaction History</h1>
        <a href="{% url 'add_transaction' %}" class="et-btn et-btn--primary">+ Add Expense</a>
    </div>

    <!-- Filter Form -->
    <form method="get" class="et-filter-form" role="search" aria-label="Filter expenses">
        <div class="et-filter-group">
            <label for="filter-category" class="et-filter-label">Category</label>
            <select name="category" id="filter-category" class="et-select et-select--sm">
                <option value="all">All Categories</option>
                {% for cat in categories %}
                    <option value="{{ cat.name }}" {% if selected_category == cat.name %}selected{% endif %}>
                        {{ cat.name }}
                    </option>
                {% endfor %}
            </select>
        </div>

        <div class="et-filter-group">
            <label for="filter-month" class="et-filter-label">Month</label>
            <input type="month" name="month" id="filter-month" class="et-input et-input--sm" value="{{ selected_month }}">
        </div>

        <div class="et-filter-actions">
            <button type="submit" class="et-btn et-btn--sm et-btn--secondary">Filter</button>
            {% if selected_category or selected_month %}
                <a href="{% url 'transaction_history' %}" class="et-btn et-btn--sm et-btn--text">Clear Filters</a>
            {% endif %}
        </div>
    </form>

    <!-- Results Table -->
    {% if transactions %}
        <table class="et-table">
            <caption class="et-sr-only">List of recorded personal expenses</caption>
            <thead>
                <tr>
                    <th scope="col">Date</th>
                    <th scope="col">Category</th>
                    <th scope="col">Note</th>
                    <th scope="col" class="et-text-right">Amount</th>
                    <th scope="col" class="et-text-center">Action</th>
                </tr>
            </thead>
            <tbody>
                {% for tx in transactions %}
                    <tr>
                        <td>{{ tx.tx_date|date:"Y-m-d" }}</td>
                        <td>
                            <span class="et-badge" style="background-color: {{ tx.category.color }};" aria-hidden="true"></span>
                            {{ tx.category.name }}
                        </td>
                        <td>{{ tx.note|default:"—" }}</td>
                        <td class="et-text-right et-monospace">${{ tx.amount|floatformat:2 }}</td>
                        <td class="et-text-center">
                            <form method="post" action="{% url 'delete_transaction' tx.id %}" style="display:inline;">
                                {% csrf_token %}
                                <button type="submit" 
                                        class="et-btn et-btn--danger-text et-btn--sm"
                                        aria-label="Delete {{ tx.category.name }} expense of ${{ tx.amount|floatformat:2 }} on {{ tx.tx_date|date:'Y-m-d' }}"
                                        onclick="return confirm('Delete this expense?');">
                                    Delete
                                </button>
                            </form>
                        </td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    {% else %}
        <div class="et-zero-state">
            <p>No transactions match your criteria.</p>
            {% if selected_category or selected_month %}
                <a href="{% url 'transaction_history' %}" class="et-btn et-btn--secondary">Clear Filters</a>
            {% else %}
                <a href="{% url 'add_transaction' %}" class="et-btn et-btn--primary">Record First Expense</a>
            {% endif %}
        </div>
    {% endif %}
</div>
{% endblock %}
```

## Current State
- `[verified]` Django's `get_object_or_404(Model, id=..., user=request.user)` idiomatically prevents IDOR vulnerabilities.

## Tests
- `test_history_isolation` — User A cannot see User B's transactions in history.
- `test_delete_own_transaction` — User A successfully deletes their own transaction.
- `test_delete_foreign_transaction_returns_404` — User A cannot delete User B's transaction.

## Constraints
- Dependencies: `02-database-schema`, `03-frontend-design-system`, `04-user-auth`, `05-add-transaction`.
