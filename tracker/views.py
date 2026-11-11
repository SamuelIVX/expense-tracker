"""
Views for the tracker application.
"""

from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

def index(request):
    """
    Smoke-test endpoint verifying server responsiveness.

    Returns:
        HttpResponse: HTTP 200 with text payload.
    """
    return HttpResponse("Expense Tracker — up.", status=200)

@login_required
def dashboard_view(request):
    """Protected view for dashboard (implemented in Spec 06)."""
    return HttpResponse("Expense Tracker — Dashboard.", status=200)

@login_required
def add_transaction_view(request):
    """Protected view for add transaction (implemented in Spec 05)."""
    return HttpResponse("Expense Tracker — Add Expense.", status=200)

@login_required
def transaction_history_view(request):
    """Protected view for transaction history (implemented in Spec 07)."""
    return HttpResponse("Expense Tracker — History.", status=200)

def login_view(request):
    """View for login page (implemented in Spec 04)."""
    return HttpResponse("Expense Tracker — Login.", status=200)

def register_view(request):
    """View for registration page (implemented in Spec 04)."""
    return HttpResponse("Expense Tracker — Register.", status=200)
