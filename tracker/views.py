"""
Views for the tracker application.
"""

from django.http import HttpResponse

def index(request):
    """
    Smoke-test endpoint verifying server responsiveness.

    Returns:
        HttpResponse: HTTP 200 with text payload.
    """
    return HttpResponse("Expense Tracker — up.", status=200)
