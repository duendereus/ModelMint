from accounts.models import OrganizationMembership
from labs.utils.branding_helper import compute_branding_context


def labs_branding_context(request):
    if not request.user.is_authenticated:
        return {}

    organization = getattr(request.user, "owned_organization", None)
    if not organization or organization.type != "lab":
        membership = (
            OrganizationMembership.objects.filter(
                user=request.user, organization__type="lab"
            )
            .select_related("organization")
            .first()
        )
        if membership:
            organization = membership.organization

    return compute_branding_context(organization)
