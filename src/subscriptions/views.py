import helpers.billing
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from helpers.subscription_pricing import get_subscription_prices
from accounts.models import Organization
from .models import OrganizationSubscription
from .tasks import notify_team_subscription_cancelled
from subscriptions import utils as subs_utils


@login_required
def organization_subscription_view(request, org_id):
    """
    View and refresh an organization's subscription.
    Only the organization owner can access this view.
    """
    organization = get_object_or_404(Organization, id=org_id)

    # Ensure only the owner can manage the plan
    if request.user != organization.owner:
        return HttpResponseForbidden(
            "You are not authorized to manage this subscription."
        )
        # return redirect(org_sub_obj.get_absolute_url())

    org_sub_obj, created = OrganizationSubscription.objects.get_or_create(
        organization=organization
    )

    if request.method == "POST":
        # Refresh subscription details from Stripe
        finished = subs_utils.refresh_active_users_subscriptions(
            org_ids=[organization.id], active_only=False
        )
        if finished:
            messages.success(
                request, "Your organization's subscription details have been refreshed."
            )
        else:
            messages.error(
                request, "Failed to refresh the subscription details. Please try again."
            )

        return redirect(org_sub_obj.get_absolute_url())

    return render(
        request,
        "subscriptions/organization_detail_view.html",
        {"subscription": org_sub_obj},
    )


@login_required
def organization_subscription_cancel_view(request, org_id):
    """
    Cancel an organization's subscription.
    Only the organization owner can perform this action.
    """
    organization = get_object_or_404(Organization, id=org_id)

    if request.user != organization.owner:
        return HttpResponseForbidden(
            "Only the organization owner can cancel the subscription."
        )

    org_sub_obj, created = OrganizationSubscription.objects.get_or_create(
        organization=organization
    )

    if request.method == "POST":
        if org_sub_obj.stripe_id and org_sub_obj.is_active_status:
            # Cancel subscription via Stripe
            sub_data = helpers.billing.cancel_subscription(
                org_sub_obj.stripe_id,
                reason="Organization decided to cancel",
                feedback="other",
                cancel_at_period_end=True,
                raw=False,
            )
            for k, v in sub_data.items():
                setattr(org_sub_obj, k, v)
            org_sub_obj.save()
            notify_team_subscription_cancelled.delay(
                organization.name,
                org_sub_obj.plan_name,
                request.user.email,
            )
            messages.success(
                request, "The organization's subscription has been cancelled."
            )

        return redirect(org_sub_obj.get_absolute_url())

    return render(
        request,
        "subscriptions/organization_cancel_view.html",
        {"subscription": org_sub_obj},
    )


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
