from django.shortcuts import render, redirect
from helpers.subscription_pricing import get_subscription_prices
from accounts.decorators import labs_only
from analytics.utils.utils import get_user_organization
from subscriptions.models import OrganizationSubscription
from subscriptions import utils as subs_utils
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from helpers import billing
from subscriptions.tasks import notify_team_subscription_cancelled


@login_required
@labs_only
def labs_organization_subscription_view(request):
    """
    View and refresh a Labs organization's subscription.
    Only the organization owner can access this view.
    """
    organization = get_user_organization(request.user)

    if not organization or request.user != organization.owner:
        return HttpResponseForbidden(
            "You are not authorized to manage this subscription."
        )

    org_sub_obj, created = OrganizationSubscription.objects.get_or_create(
        organization=organization
    )

    if request.method == "POST":
        finished = subs_utils.refresh_active_users_subscriptions(
            org_ids=[organization.id], active_only=False
        )
        if finished:
            messages.success(
                request, "Your organization's subscription has been refreshed."
            )
        else:
            messages.error(request, "Failed to refresh subscription. Please try again.")

        return redirect(org_sub_obj.get_absolute_url())

    return render(
        request,
        "labs/subscriptions/organization_detail_view.html",
        {"subscription": org_sub_obj},
    )


@login_required
@labs_only
def labs_organization_subscription_cancel_view(request):
    """
    Cancel a Labs organization's subscription.
    Only the organization owner can perform this action.
    """
    organization = get_user_organization(request.user)

    if not organization or request.user != organization.owner:
        return HttpResponseForbidden(
            "Only the organization owner can cancel the subscription."
        )

    org_sub_obj, created = OrganizationSubscription.objects.get_or_create(
        organization=organization
    )

    if request.method == "POST":
        if org_sub_obj.stripe_id and org_sub_obj.is_active_status:
            sub_data = billing.cancel_subscription(
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
        "labs/subscriptions/organization_cancel_view.html",
        {"subscription": org_sub_obj},
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
