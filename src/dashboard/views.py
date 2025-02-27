from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def dashboard_home(request):
    """
    View for the dashboard home page.
    Ensures only authenticated users can access it.
    """

    user = request.user  # Get logged-in user

    # Get owned organization (OneToOneField)
    owned_org = getattr(user, "owned_organization", None)

    # Get organization membership (ManyToManyField)
    member_org = user.organization.first() if user.organization.exists() else None

    context = {
        "owned_org": owned_org,
        "member_org": member_org,
    }

    return render(request, "dashboard/home.html", context)
