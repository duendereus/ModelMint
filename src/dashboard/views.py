from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from accounts.models import OrganizationMembership


@login_required
def dashboard_home(request):
    """
    View for the dashboard home page.
    Ensures only authenticated users can access it.
    """

    context = {}

    return render(request, "dashboard/home.html", context)
