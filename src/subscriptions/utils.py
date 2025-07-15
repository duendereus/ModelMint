import helpers.billing
from customers.models import OrganizationCustomer
from subscriptions.models import Subscription, OrganizationSubscription
from .constants import PLAN_LIMITS, LAB_PLAN_LIMITS
from django.utils.timezone import now


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

    qs = qs.filter(stripe_id__isnull=False).exclude(stripe_id="")  # 🔧 importante
    qs_count = qs.count()
    complete_count = 0

    for obj in qs:
        if verbose:
            print(
                "[DEBUG] Updating org:",
                obj.organization.name,
                "| Sub ID:",
                obj.stripe_id,
                "| Plan:",
                obj.subscription,
                "| Current End:",
                obj.current_period_end,
            )
        try:
            sub_data = helpers.billing.get_subscription(obj.stripe_id, raw=False)
            print(f"[DEBUG] Stripe response for {obj.stripe_id} →", sub_data)
            for k, v in sub_data.items():
                setattr(obj, k, v)
            obj.save()
            complete_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to refresh sub {obj.stripe_id}: {e}")

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
    """
    Returns the limits dictionary for the current plan,
    depending on whether it's a DaaS or Labs organization.
    """
    try:
        sub = organization.subscription
        if sub and sub.subscription and sub.is_active_status:
            plan_name = sub.subscription.name
            if organization.type == "lab":
                return LAB_PLAN_LIMITS.get(plan_name, LAB_PLAN_LIMITS["Free"])
            return PLAN_LIMITS.get(plan_name)
    except AttributeError:
        pass

    if organization.type == "lab":
        return LAB_PLAN_LIMITS["Free"]

    # For DaaS orgs without plan, return None (access denied)
    return None


def can_add_member(organization):
    """
    Returns True if the organization can add another member based on its subscription plan.
    """
    limits = get_plan_limits(organization)
    if limits is None:
        return False  # No subscription, no member additions

    max_members = limits.get("max_members", 1)
    if max_members == float("inf"):
        return True

    current_member_count = organization.members.count() + 1  # Include the owner
    return current_member_count < max_members


def can_upload_data(organization):
    """
    Checks if the organization is allowed to upload more data this month.
    Returns True if allowed, False if limit reached or no subscription.
    """
    limits = get_plan_limits(organization)
    if limits is None:
        return False

    max_uploads = limits.get("max_uploads_per_month", 1)
    if max_uploads == float("inf"):
        return True

    start_of_month = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    uploads_this_month = organization.data_uploads.filter(
        created_at__gte=start_of_month
    ).count()

    return uploads_this_month < max_uploads


def can_view_more_reports(organization):
    limits = get_plan_limits(organization)
    if limits is None:
        return False  # No subscription = no access to reports

    max_reports = limits.get("max_reports", 3)
    if max_reports == float("inf"):
        return True

    current_reports = organization.data_uploads.filter(processed=True).count()
    return current_reports < max_reports


def can_download_pdf_reports(organization):
    limits = get_plan_limits(organization)
    if limits is None:
        return False
    return limits.get("allow_pdf_download", False)
