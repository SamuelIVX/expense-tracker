"""
Views for the tracker application.
"""

import calendar
import csv
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import Category, Transaction, UserProfile
from .forms import RegisterForm, TransactionForm
from .constants import DEFAULT_MONTHLY_BUDGET
from .queries import (
    get_monthly_spending_summary,
    get_monthly_category_breakdown,
    get_recent_transactions,
    get_filtered_transactions,
)

def index(request):
    """
    Root endpoint. Redirects authenticated users to the dashboard and
    unauthenticated visitors to the login page.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')

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
    category_breakdown_data = [
        {
            'category_id': item['category_id'],
            'name': item['name'],
            'color': item['color'],
            'total': float(item['total']),
            'tx_count': item['tx_count'],
            'percentage': item['percentage'],
        }
        for item in category_breakdown
    ]
    category_breakdown_json = json.dumps(category_breakdown_data)
    recent_transactions = get_recent_transactions(user_id, limit=5)

    profile, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'monthly_budget': DEFAULT_MONTHLY_BUDGET}
    )
    budget = profile.monthly_budget
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
        'category_breakdown_data': category_breakdown_data,
        'category_breakdown_json': category_breakdown_json,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'tracker/dashboard.html', context)

@login_required
def update_budget_view(request):
    """
    Updates the authenticated user's monthly budget benchmark via POST.
    Rejects non-numeric, negative, zero, or sub-cent fractional values.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    raw_budget = request.POST.get('monthly_budget', '').strip()
    try:
        new_budget = Decimal(raw_budget)
        if new_budget.as_tuple().exponent < -2:
            raise ValidationError("Budget cannot have fractional cents beyond two decimal places.")
        if new_budget <= Decimal('0.00') or new_budget > Decimal('999999.99'):
            raise ValidationError("Budget must be between $0.01 and $999,999.99.")
    except (InvalidOperation, ValidationError, TypeError, ValueError):
        messages.error(request, "Please enter a valid monthly budget amount between $0.01 and $999,999.99.")
        return redirect('dashboard')

    profile, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'monthly_budget': DEFAULT_MONTHLY_BUDGET}
    )
    profile.monthly_budget = new_budget
    profile.save()
    messages.success(request, f"Monthly budget successfully updated to ${new_budget:.2f}.")
    return redirect('dashboard')

def _sanitize_csv_cell(value):
    """
    Prevents CSV / Formula injection attacks (CWE-1236 / OWASP ASVS).
    If a cell value starts with '=', '+', '-', '@', tab, or carriage return,
    prepends a single quote to prevent spreadsheet formula execution.
    """
    if value is None:
        return ''
    str_val = str(value)
    if str_val.startswith(('=', '+', '-', '@', '\t', '\r')):
        return f"'{str_val}"
    return str_val

@login_required
def export_transactions_csv_view(request):
    """
    Exports filtered or complete transaction history for the authenticated user as a downloadable CSV.
    Respects active category, month, and search query filters, with CSV formula injection protection.
    """
    category_param = request.GET.get('category', '').strip()
    month_param = request.GET.get('month', '').strip()
    search_param = request.GET.get('q', '').strip()

    category_id = None
    if category_param.isascii() and category_param.isdigit() and len(category_param) <= 10:
        try:
            category_id = int(category_param)
        except (ValueError, OverflowError):
            category_id = None

    start_date = None
    end_date = None
    if month_param:
        try:
            parts = month_param.split('-')
            if len(parts) == 2:
                year = int(parts[0])
                month_num = int(parts[1])
                if 1 <= month_num <= 12 and 1900 <= year <= 2100:
                    _, last_day = calendar.monthrange(year, month_num)
                    start_date = date(year, month_num, 1)
                    end_date = date(year, month_num, last_day)
        except (ValueError, TypeError):
            start_date = None
            end_date = None

    transactions = get_filtered_transactions(
        user_id=request.user.id,
        category_id=category_id,
        start_date=start_date,
        end_date=end_date,
        search=search_param if search_param else None,
    )

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Category', 'Amount', 'Description'])

    for tx in transactions:
        writer.writerow([
            tx['tx_date'].strftime('%Y-%m-%d'),
            _sanitize_csv_cell(tx['category_name']),
            f"{tx['amount']:.2f}",
            _sanitize_csv_cell(tx['note']),
        ])

    return response

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
    """
    Renders filterable and paginated list of transactions for the authenticated user.
    Supports filtering by category, calendar month, and substring search on notes.
    """
    category_param = request.GET.get('category', '').strip()
    month_param = request.GET.get('month', '').strip()
    search_param = request.GET.get('q', '').strip()

    category_id = None
    if category_param.isascii() and category_param.isdigit() and len(category_param) <= 10:
        try:
            category_id = int(category_param)
        except (ValueError, OverflowError):
            category_id = None

    start_date = None
    end_date = None
    if month_param:
        try:
            parts = month_param.split('-')
            if len(parts) == 2:
                year = int(parts[0])
                month_num = int(parts[1])
                if 1 <= month_num <= 12 and 1900 <= year <= 2100:
                    _, last_day = calendar.monthrange(year, month_num)
                    start_date = date(year, month_num, 1)
                    end_date = date(year, month_num, last_day)
        except (ValueError, TypeError):
            start_date = None
            end_date = None

    transactions = get_filtered_transactions(
        user_id=request.user.id,
        category_id=category_id,
        start_date=start_date,
        end_date=end_date,
        search=search_param if search_param else None,
    )

    filtered_count = len(transactions)
    filtered_total = sum((t['amount'] for t in transactions), Decimal('0.00'))

    # Paginate results at 15 items per page
    paginator = Paginator(transactions, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Preserve active filter parameters across pagination links
    query_dict = request.GET.copy()
    if 'page' in query_dict:
        del query_dict['page']
    preserved_query = query_dict.urlencode()

    categories = Category.objects.all().order_by('name')

    context = {
        'page_obj': page_obj,
        'categories': categories,
        'filtered_count': filtered_count,
        'filtered_total': filtered_total,
        'selected_category': category_id,
        'selected_month': month_param,
        'search_query': search_param,
        'preserved_query': preserved_query,
    }
    return render(request, 'tracker/history.html', context)

@login_required
def delete_transaction_view(request, pk):
    """
    Safely deletes a transaction owned by the authenticated user via POST.
    Prevents unauthorized deletion of transactions belonging to other users.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    tx = get_object_or_404(Transaction, pk=pk, user=request.user)
    amount = tx.amount
    category_name = tx.category.name
    tx.delete()
    messages.success(request, f"Deleted expense of ${amount:.2f} for {category_name}.")
    return redirect('transaction_history')

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
