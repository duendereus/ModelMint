from accounts.models import OrganizationMembership


def can_manage_membership(requesting_user, target_membership, organization):
    """
    Checks if the requesting_user can manage (edit/delete) the target_membership.
    """
    if not organization or target_membership.organization != organization:
        return False

    is_owner = organization.owner == requesting_user
    is_admin = OrganizationMembership.objects.filter(
        user=requesting_user, organization=organization, role="admin"
    ).exists()

    target_user = target_membership.user
    is_target_owner = target_user == organization.owner
    is_self = requesting_user == target_user

    # 🚫 No puede actuar sobre sí mismo ni sobre el owner si no es el owner
    if is_self or is_target_owner:
        return False

    if is_owner:
        return True

    if is_admin and target_membership.role == "member":
        return True

    return False
