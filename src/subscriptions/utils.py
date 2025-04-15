import helpers.billing
from customers.models import OrganizationCustomer
from subscriptions.models import Subscription, OrganizationSubscription
from .constants import PLAN_LIMITS


def refresh_active_users_subscriptions(
    org_ids=None,
    active_only=True,
    days_left=-1,
    days_ago=-1,
    day_start=-1,
    day_end=-1,
    verbose=False,
):
    qs = OrganizationSubscription.objects.all()
    if active_only:
        qs = qs.by_active_trialing()
    if org_ids is not None:
        qs = qs.filter(organization_id__in=org_ids)
    if days_ago > -1:
        qs = qs.by_days_ago(days_ago=days_ago)
    if days_left > -1:
        qs = qs.by_days_left(days_left=days_left)
    if day_start > -1 and day_end > -1:
        qs = qs.by_range(days_start=day_start, days_end=day_end, verbose=verbose)

    complete_count = 0
    qs_count = qs.count()
    for obj in qs:
        if verbose:
            print(
                "Updating organization",
                obj.organization.name,
                obj.subscription,
                obj.current_period_end,
            )
        if obj.stripe_id:
            sub_data = helpers.billing.get_subscription(obj.stripe_id, raw=False)
            for k, v in sub_data.items():
                setattr(obj, k, v)
            obj.save()
            complete_count += 1
    return complete_count == qs_count


def clear_dangling_subs():
    qs = OrganizationCustomer.objects.filter(stripe_id__isnull=False)
    for org_customer in qs:
        organization = org_customer.organization
        customer_stripe_id = org_customer.stripe_id
        print(
            f"Sync {organization.name} - {customer_stripe_id} subs and remove old ones"
        )
        subs = helpers.billing.get_customer_active_subscriptions(customer_stripe_id)

        for sub in subs:
            existing_org_subs_qs = OrganizationSubscription.objects.filter(
                stripe_id__iexact=f"{sub.id}".strip()
            )
            if existing_org_subs_qs.exists():
                continue
            helpers.billing.cancel_subscription(
                sub.id,
                reason="Dangling active subscription",
                cancel_at_period_end=False,
            )


def sync_subs_group_permissions():
    qs = Subscription.objects.filter(active=True)
    for obj in qs:
        sub_perms = obj.permissions.all()
        for group in obj.groups.all():
            group.permissions.set(sub_perms)

def get_plan_limits(organization):
    try:
        sub = organization.subscription
        if sub and sub.subscription and sub.subscription.name in PLAN_LIMITS:
            return PLAN_LIMITS[sub.subscription.name]
    except AttributeError:
        pass
    return PLAN_LIMITS["Starter Plan"]  # fallback