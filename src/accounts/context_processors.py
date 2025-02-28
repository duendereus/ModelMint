from accounts.models import OrganizationMembership


def organization_context(request):
    """Ensure organization details are available in all templates."""
    if request.user.is_authenticated:
        user = request.user

        # Get owned organization
        owned_org = getattr(user, "owned_organization", None)

        # Get organization membership
        membership = (
            OrganizationMembership.objects.filter(user=user)
            .select_related("organization")
            .first()
        )
        member_org = membership.organization if membership else None

        return {
            "owned_org": owned_org,
            "member_org": member_org,
            "membership_role": membership.role if membership else None,
        }
    return {}
