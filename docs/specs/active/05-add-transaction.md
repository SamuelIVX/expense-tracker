# Spec: Add Transaction

## Applicable Skills
- `better-accessibility`: Accessible forms, `<label for>` explicit association, `aria-describedby` linking errors, `aria-invalid="true"` state handling.
- `owasp-security`: A01 Broken Access Control (server-side user ownership binding), A05 Injection defense, numeric boundary constraints.
- `better-writing`: Clear field labels, contextual placeholder guidance, affirmative button copy ("Save Expense").

## Objective
Build the "Add Expense" feature: an accessible, validated form allowing authenticated users to log a new
expense (amount, category, transaction date, and optional note). Validate inputs on both client and server,
assign row-level ownership directly from `request.user`, enforce accessible error states, and persist to MySQL.
This satisfies the form handling, input validation, and data persistence objectives of the course.

> **Ownership:** Beginner teammate, with form and view skeletons provided. Teammate styles template and validates UI feedback.

## Scope
- Package: `expense-tracker`
- Modifies (creates):
  - `templates/tracker/add_transaction.html` (the expense submission form)
- Modifies (existing):
  - `tracker/forms.py` (adds `TransactionForm`)
  - `tracker/views.py` (adds `add_transaction_view` decorated with `@login_required`)
  - `tracker/urls.py` (registers `/add/`)
- Off-limits: `schema.sql`, `tracker/models.py` (02); `style.css` (03); auth views (04).

## Non-Goals
- No bulk transaction upload (CSV/bank sync) in v1.
- No receipt file/photo attachments.
- No recurring or split expenses.

## Invariants
- The `user` foreign key MUST ALWAYS be assigned server-side from `request.user` — never accepted as a client form field or query parameter. [OWASP A01 / Broken Access Control Prevention]
- `amount` MUST be strictly greater than 0.00 and capped at 999,999.99 (`min="0.01"`, `max="999999.99"`). [Monetary & Overflow Invariant]
- Category selection MUST be constrained to existing `Category` records in the database.
- Every form field displaying an error MUST set `aria-invalid="true"` on the input and link the error message via `aria-describedby`. [Accessibility / WCAG 3.3.1]
- Server-side validation MUST run independently of client-side validation — bypassing client JavaScript must not permit invalid data writes. [Defense in Depth]

## Requirements
1. WHEN an authenticated user GETs `/add/`, THE SYSTEM SHALL render `templates/tracker/add_transaction.html` containing:
   - `amount` input (`type="number"`, `step="0.01"`, `min="0.01"`, `max="999999.99"`, required)
   - `category` `<select>` dropdown populated dynamically with all records from `Category.objects.all()`
   - `tx_date` date picker (`type="date"`, required, defaulting to today's date)
   - `note` text input (`maxlength="255"`, optional)
   - "Save Expense" submit button
2. WHEN the form is submitted via POST with valid data, THE SYSTEM SHALL:
   - Assign `transaction.user = request.user`
   - Save the record to the `tracker_transaction` table
   - Set a flash message `"Expense of $<amount> saved."`
   - Redirect the user to `/history/`
3. WHEN `amount` is missing, ≤ 0, or exceeds 999,999.99, THE SYSTEM SHALL re-render the form displaying `"Amount must be between $0.01 and $999,999.99."` and set `aria-invalid="true"`.
4. WHEN `category` is invalid or missing, THE SYSTEM SHALL re-render the form displaying `"Please select a valid category."`.
5. THE SYSTEM SHALL apply class `.et-form` to the `<form>` element so `static/js/ui.js` triggers the "Saving..." loading state upon submission.

## Failure Modes & Edge Cases
1. **Attempting to Spoof User ID:** Any client attempt to inject `user_id` in POST data SHALL be completely ignored; the view explicitly sets `form.instance.user = request.user`.
2. **Future Dates:** Transactions with dates in the future are permitted (e.g. planned bills), but empty date values fail validation.
3. **High-Precision Decimals:** Submissions with more than 2 decimal places (e.g. `12.345`) SHALL be rejected by Django's `DecimalField` validator.

## Acceptance Criteria
- [ ] Navigating to `/add/` while logged in displays the form with today's date pre-filled and categories populated.
- [ ] Submitting `$45.50` for `Food` creates a row in MySQL with `user_id = <logged_in_user_id>`.
- [ ] Screen readers announce validation errors linked via `aria-describedby`.
- [ ] Submitting negative or zero amounts displays an inline error without writing to the database.
- [ ] Successful submission redirects to `/history/` with a success alert banner.
- [ ] Button disables and shows "Saving..." during POST processing.

## Design

### `tracker/forms.py` (TransactionForm Addition)
```python
from decimal import Decimal
from datetime import date
from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator
from .models import Transaction, Category

class TransactionForm(forms.ModelForm):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.01'), message="Amount must be at least $0.01."),
            MaxValueValidator(Decimal('999999.99'), message="Amount cannot exceed $999,999.99."),
        ],
        widget=forms.NumberInput(attrs={
            'class': 'et-input',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0.01',
            'max': '999999.99',
            'required': True,
        })
    )

    class Meta:
        model = Transaction
        fields = ['amount', 'category', 'tx_date', 'note']
        widgets = {
            'category': forms.Select(attrs={
                'class': 'et-select',
                'required': True,
            }),
            'tx_date': forms.DateInput(attrs={
                'class': 'et-input',
                'type': 'date',
                'required': True,
            }),
            'note': forms.TextInput(attrs={
                'class': 'et-input',
                'placeholder': 'Optional (e.g., Grocery run, electric bill)',
                'maxlength': '255',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get('tx_date'):
            self.initial['tx_date'] = date.today().isoformat()
        self.fields['category'].queryset = Category.objects.all()
        self.fields['category'].empty_label = "-- Select Category --"
```

### `tracker/views.py` (Add Transaction View)
```python
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import TransactionForm

@login_required
def add_transaction_view(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.save()
            messages.success(request, f"Expense of ${transaction.amount:.2f} saved successfully.")
            return redirect('transaction_history')
    else:
        form = TransactionForm()

    return render(request, 'tracker/add_transaction.html', {'form': form})
```

### `templates/tracker/add_transaction.html` (Accessible Template)
```html
{% extends "base.html" %}

{% block title %}Add Expense &bull; Expense Tracker{% endblock %}

{% block content %}
<div class="et-card et-card--form">
    <h1 class="et-card__title">Record an Expense</h1>
    <form method="post" class="et-form" novalidate>
        {% csrf_token %}
        
        <div class="et-form-group">
            <label for="{{ form.amount.id_for_label }}" class="et-label">Amount ($)</label>
            <input type="number" 
                   name="{{ form.amount.name }}" 
                   id="{{ form.amount.id_for_label }}"
                   step="0.01" min="0.01" max="999999.99"
                   value="{{ form.amount.value|default:'' }}"
                   class="et-input {% if form.amount.errors %}et-input--error{% endif %}"
                   {% if form.amount.errors %}aria-invalid="true" aria-describedby="amount-error"{% endif %}
                   required>
            {% if form.amount.errors %}
                <span id="amount-error" class="et-field-error" role="alert">{{ form.amount.errors.0 }}</span>
            {% endif %}
        </div>

        <div class="et-form-group">
            <label for="{{ form.category.id_for_label }}" class="et-label">Category</label>
            {{ form.category }}
            {% if form.category.errors %}
                <span id="category-error" class="et-field-error" role="alert">{{ form.category.errors.0 }}</span>
            {% endif %}
        </div>

        <div class="et-form-group">
            <label for="{{ form.tx_date.id_for_label }}" class="et-label">Date</label>
            {{ form.tx_date }}
            {% if form.tx_date.errors %}
                <span id="date-error" class="et-field-error" role="alert">{{ form.tx_date.errors.0 }}</span>
            {% endif %}
        </div>

        <div class="et-form-group">
            <label for="{{ form.note.id_for_label }}" class="et-label">Note (Optional)</label>
            {{ form.note }}
            {% if form.note.errors %}
                <span id="note-error" class="et-field-error" role="alert">{{ form.note.errors.0 }}</span>
            {% endif %}
        </div>

        <div class="et-form-actions">
            <button type="submit" class="et-btn et-btn--primary">Save Expense</button>
            <a href="{% url 'dashboard' %}" class="et-btn et-btn--secondary">Cancel</a>
        </div>
    </form>
</div>
{% endblock %}
```

## Current State
- `[verified]` HW4 in Sam's coursework verifies form handling and input validation structure.

## Tests
- `test_add_transaction_success` — valid POST saves record with `user = request.user`.
- `test_add_transaction_negative_amount_fails` — negative amount rejected with field error.
- `test_add_transaction_requires_login` — unauthenticated POST redirects to login.

## Constraints
- Dependencies: `02-database-schema`, `03-frontend-design-system`, `04-user-auth` must merge first.
- Downstream: `06-dashboard` and `07-transaction-history` consume the transactions saved by this spec.
