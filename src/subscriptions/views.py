from django.shortcuts import render
from helpers.subscription_pricing import get_subscription_prices


def subscription_price_view(request, interval="month"):
    """
    Subscription pricing page.
    """
    object_list, active = get_subscription_prices(interval)

    return render(
        request,
        "subscriptions/pricing.html",
        {"object_list": object_list, "active": active},
    )
