from django.shortcuts import render, redirect
from helpers.subscription_pricing import get_subscription_prices
from django.contrib import messages


def home(request):
    """
    Public homepage view.
    If the user is authenticated and has an active subscription, redirect to the dashboard.
    """
    object_list, active = get_subscription_prices()

    if request.user.is_authenticated:
        if active:  # If the user has an active subscription
            messages.info(request, f"Welcome back, {request.user.username}!")
            return redirect("dashboard:dashboard_home")  # Redirect to dashboard

    context = {"object_list": object_list, "active": active}
    return render(request, "home/home.html", context)


def labs_landing_view(request):
    """
    Public landing page explaining the Labs offering.
    """
    prices, _ = get_subscription_prices(for_labs=True)
    return render(request, "home/labs_landing.html", {"labs_prices": prices})
