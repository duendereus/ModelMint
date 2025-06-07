import helpers.billing
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import HttpResponseBadRequest

from subscriptions.models import (
    SubscriptionPrice,
    Subscription,
    OrganizationSubscription,
)
from customers.models import OrganizationCustomer

BASE_URL = settings.BASE_URL


def product_price_redirect_view(request, price_id=None, *args, **kwargs):
    request.session["checkout_subscription_price_id"] = price_id
    return redirect("checkouts:stripe-checkout-start")


@login_required
def checkout_redirect_view(request):
    checkout_subscription_price_id = request.session.get(
        "checkout_subscription_price_id"
    )
    try:
        obj = SubscriptionPrice.objects.get(id=checkout_subscription_price_id)
    except SubscriptionPrice.DoesNotExist:
        obj = None

    if checkout_subscription_price_id is None or obj is None:
        return redirect("subscriptions:pricing")

    user = request.user
    if not hasattr(user, "owned_organization"):
        return HttpResponseBadRequest("You must own an organization to subscribe.")

    organization = user.owned_organization
    try:
        customer_stripe_id = organization.organizationcustomer.stripe_id
    except OrganizationCustomer.DoesNotExist:
        return HttpResponseBadRequest("No Stripe customer found for your organization.")

    success_url_path = reverse("checkouts:stripe-checkout-end")
    pricing_url_path = reverse("subscriptions:pricing")
    success_url = f"{BASE_URL}{success_url_path}"
    cancel_url = f"{BASE_URL}{pricing_url_path}"
    price_stripe_id = obj.stripe_id

    url = helpers.billing.start_checkout_session(
        customer_stripe_id,
        success_url=success_url,
        cancel_url=cancel_url,
        price_stripe_id=price_stripe_id,
        raw=False,
    )
    return redirect(url)


@login_required
def checkout_finalize_view(request):
    session_id = request.GET.get("session_id")
    checkout_data = helpers.billing.get_checkout_customer_plan(session_id)
    plan_id = checkout_data.pop("plan_id")
    customer_id = checkout_data.pop("customer_id")
    sub_stripe_id = checkout_data.pop("sub_stripe_id")
    subscription_data = {**checkout_data}

    user = request.user
    if not hasattr(user, "owned_organization"):
        return HttpResponseBadRequest("You must own an organization to subscribe.")

    organization = user.owned_organization

    try:
        sub_obj = Subscription.objects.get(subscriptionprice__stripe_id=plan_id)
    except Subscription.DoesNotExist:
        return HttpResponseBadRequest("Invalid subscription plan.")

    org_sub, created = OrganizationSubscription.objects.get_or_create(
        organization=organization
    )

    updated_sub_options = {
        "subscription": sub_obj,
        "stripe_id": sub_stripe_id,
        "user_cancelled": False,
        **subscription_data,
    }

    # Cancel old subscription if changing plans
    if not created and org_sub.stripe_id != sub_stripe_id:
        try:
            helpers.billing.cancel_subscription(
                org_sub.stripe_id, reason="Auto-ended, new membership", feedback="other"
            )
        except Exception:
            pass

    # Assign new subscription
    for k, v in updated_sub_options.items():
        setattr(org_sub, k, v)

    org_sub.save()
    messages.success(
        request, "Success! Your organization's subscription has been updated."
    )
    return redirect(org_sub.get_absolute_url())
