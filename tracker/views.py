"""
Views for the tracker application.
"""

from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError, transaction
from .forms import RegisterForm, TransactionForm

def index(request):
    """
    Smoke-test endpoint verifying server responsiveness.

    Returns:
        HttpResponse: HTTP 200 with text payload.
    """
    return HttpResponse("Expense Tracker — up.", status=200)

@login_required
def dashboard_view(request):
    """Protected view for dashboard (full metrics implemented in Spec 06)."""
    return render(request, 'tracker/dashboard.html')

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
