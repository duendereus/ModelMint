from django.shortcuts import render
from helpers.subscription_pricing import get_subscription_prices


def home(request):
    object_list, active = get_subscription_prices()
    context = {"object_list": object_list, "active": active}
    return render(request, "home/home.html", context)
