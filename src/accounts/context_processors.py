from accounts.models import OrganizationMembership
from subscriptions.utils import get_plan_limits


def organization_context(request):
    """Ensure organization details are available in all templates."""
    if request.user.is_authenticated:
        user = request.user

        owned_org = getattr(user, "owned_organization", None)

        membership = (
            OrganizationMembership.objects.filter(user=user)
            .select_related("organization")
            .first()
        )
        member_org = membership.organization if membership else None
        current_org = owned_org or member_org

        plan_name = None
        if (
            current_org
            and hasattr(current_org, "subscription")
            and current_org.subscription
        ):
            plan_name = current_org.subscription.plan_name

        return {
            "owned_org": owned_org,
            "member_org": member_org,
            "membership_role": membership.role if membership else None,
            "current_plan_name": plan_name,
        }

    return {}
