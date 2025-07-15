import helpers.billing
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import HttpResponseBadRequest
from accounts.decorators import labs_only
from analytics.utils.utils import get_user_organization
from subscriptions.models import (
    SubscriptionPrice,
    Subscription,
    OrganizationSubscription,
)
from customers.models import OrganizationCustomer
from checkouts.tasks import notify_team_new_subscription

BASE_URL = settings.BASE_URL


@login_required(login_url="labs:labs_login")
@labs_only
def labs_checkout_redirect_view(request, price_id):
    organization = get_user_organization(request.user)
    try:
        customer_stripe_id = organization.organizationcustomer.stripe_id
    except OrganizationCustomer.DoesNotExist:
        return HttpResponseBadRequest("No Stripe customer found for your organization.")

    try:
        price_obj = SubscriptionPrice.objects.get(id=price_id)
    except SubscriptionPrice.DoesNotExist:
        return HttpResponseBadRequest("Invalid price ID.")

    success_url = reverse("labs:labs_checkout_finalize")
    if not success_url.endswith("?session_id={CHECKOUT_SESSION_ID}"):
        success_url += "?session_id={CHECKOUT_SESSION_ID}"

    success_url = f"{BASE_URL}{success_url}"
    cancel_url = f"{BASE_URL}{reverse('labs:labs_pricing')}"

    url = helpers.billing.start_checkout_session(
        customer_id=customer_stripe_id,
        success_url=success_url,
        cancel_url=cancel_url,
        price_stripe_id=price_obj.stripe_id,
        raw=False,
    )
    return redirect(url)


@login_required(login_url="labs:labs_login")
@labs_only
def labs_checkout_finalize(request):
    session_id = request.GET.get("session_id")
    if not session_id:
        return HttpResponseBadRequest("Missing session ID.")

    checkout_data = helpers.billing.get_checkout_customer_plan(session_id)

    print("🔍 DEBUG checkout_data:", checkout_data)

    plan_id = checkout_data.pop("plan_id")
    customer_id = checkout_data.pop("customer_id")
    sub_stripe_id = checkout_data.pop("sub_stripe_id")

    try:
        sub_obj = Subscription.objects.get(subscriptionprice__stripe_id=plan_id)
    except Subscription.DoesNotExist:
        return HttpResponseBadRequest("Invalid subscription plan.")

    organization = get_user_organization(request.user)
    org_sub, created = OrganizationSubscription.objects.get_or_create(
        organization=organization
    )

    # Cancel previous if needed
    if not created and org_sub.stripe_id != sub_stripe_id:
        try:
            helpers.billing.cancel_subscription(
                org_sub.stripe_id, reason="Auto-ended, new membership", feedback="other"
            )
        except Exception:
            pass

    for k, v in {
        "subscription": sub_obj,
        "stripe_id": sub_stripe_id,
        "user_cancelled": False,
        **checkout_data,
    }.items():
        setattr(org_sub, k, v)

    org_sub.save()
    notify_team_new_subscription.delay(
        organization.name,
        sub_obj.name,
        request.user.email,
    )
    messages.success(
        request, "Success! Your organization's subscription has been updated."
    )
    return redirect(org_sub.get_absolute_url())
