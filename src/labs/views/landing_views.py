from django.shortcuts import render, redirect
from helpers.subscription_pricing import get_subscription_prices
from accounts.utils import get_user_organization_type


def labs_landing_view(request):
    """
    Public landing page for Labs.
    - Redirects authenticated Labs users to their Labs dashboard.
    - Redirects authenticated DaaS users to the DaaS dashboard.
    - Shows Labs subscription plans to unauthenticated users.
    """
    prices, active = get_subscription_prices(for_labs=True)

    if request.user.is_authenticated:
        org_type = get_user_organization_type(request.user)
        if org_type == "lab":
            return redirect("labs:labs_dashboard_home")
        else:
            return redirect("dashboard:dashboard_home")

    context = {"labs_prices": prices, "active": active}
    return render(request, "labs/labs_landing.html", context)
