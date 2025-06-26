from django.shortcuts import render
from helpers.subscription_pricing import get_subscription_prices


def labs_pricing_view(request):
    """
    Labs subscription pricing page.
    """
    object_list, _ = get_subscription_prices(for_labs=True)

    return render(
        request,
        "labs/labs_pricing.html",
        {"object_list": object_list},
    )
