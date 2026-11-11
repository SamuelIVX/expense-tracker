"""
Views for the tracker application.
"""

import calendar
from decimal import Decimal
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.utils import timezone
from .forms import RegisterForm, TransactionForm
from .constants import DEFAULT_MONTHLY_BUDGET
from .queries import (
    get_monthly_spending_summary,
    get_monthly_category_breakdown,
    get_recent_transactions,
)

def index(request):
    """
    Smoke-test endpoint verifying server responsiveness.

    Returns:
        HttpResponse: HTTP 200 with text payload.
    """
    return HttpResponse("Expense Tracker — up.", status=200)

@login_required
def dashboard_view(request):
    """
    Renders user spending metrics, monthly budget progress, category breakdown,
    and recent activity aggregated through parameterized raw SQL queries.
    """
    today = timezone.localdate()
    start_of_month = today.replace(day=1)
    _, last_day = calendar.monthrange(today.year, today.month)
    end_of_month = today.replace(day=last_day)
    month_name = today.strftime('%B %Y')

    user_id = request.user.id
    summary = get_monthly_spending_summary(user_id, start_of_month, end_of_month)
    total_spent = summary['total_spent']
    tx_count = summary['tx_count']

    category_breakdown = get_monthly_category_breakdown(
        user_id, start_of_month, end_of_month, total_spent=total_spent
    )
    recent_transactions = get_recent_transactions(user_id, limit=5)

    budget = DEFAULT_MONTHLY_BUDGET
    if budget > 0:
        budget_ratio = (total_spent / budget) * Decimal('100')
    else:
        budget_ratio = Decimal('0')

    progress_width = min(budget_ratio, Decimal('100.0'))
    budget_remaining = budget - total_spent
    is_over_budget = total_spent > budget
    over_budget_amount = total_spent - budget if is_over_budget else Decimal('0')

    if budget_ratio >= Decimal('90.0'):
        progress_class = "et-progress__bar--danger"
    elif budget_ratio >= Decimal('70.0'):
        progress_class = "et-progress__bar--warn"
    else:
        progress_class = ""

    context = {
        'month_name': month_name,
        'total_spent': total_spent,
        'tx_count': tx_count,
        'budget': budget,
        'budget_percentage': round(float(budget_ratio), 1),
        'progress_width': round(float(progress_width), 1),
        'budget_remaining': budget_remaining,
        'is_over_budget': is_over_budget,
        'over_budget_amount': over_budget_amount,
        'progress_class': progress_class,
        'category_breakdown': category_breakdown,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'tracker/dashboard.html', context)

@login_required
def add_transaction_view(request):
    """
    Renders and processes the expense transaction entry form.
    Associates the newly created transaction with the authenticated user.
    """
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction_obj = form.save(commit=False)
            transaction_obj.user = request.user
            transaction_obj.save()
            messages.success(
                request,
                f"Added expense: ${transaction_obj.amount:.2f} for {transaction_obj.category.name}."
            )
            return redirect('transaction_history')
    else:
        form = TransactionForm()

    return render(request, 'tracker/add_transaction.html', {'form': form})

@login_required
def transaction_history_view(request):
    """Protected view for transaction history (full filters implemented in Spec 07)."""
    return render(request, 'tracker/history.html')

def register_view(request):
    """
    Handles user registration. Authenticated users are redirected to the dashboard.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
            except IntegrityError:
                form.add_error('username', "A user with that username already exists.")
                return render(request, 'registration/register.html', {'form': form})
            login(request, user)
            messages.success(request, f"Welcome to Expense Tracker, {user.username}!")
            return redirect('dashboard')
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {'form': form})
