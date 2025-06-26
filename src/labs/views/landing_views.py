from django.shortcuts import render
from helpers.subscription_pricing import get_subscription_prices


def labs_landing_view(request):
    """
    Public landing page explaining the Labs offering.
    """
    prices, _ = get_subscription_prices(for_labs=True)
    return render(request, "labs/labs_landing.html", {"labs_prices": prices})
