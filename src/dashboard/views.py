from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages


@login_required
def dashboard_home(request):
    """
    View for the dashboard home page.
    Ensures only authenticated users can access it.
    """
    user = request.user  # Get the logged-in user
    organization = user.organizations.first() if user.organizations.exists() else None

    context = {
        "organization": organization,
    }

    return render(request, "dashboard/home.html", context)
