from django import template

register = template.Library()


@register.simple_tag
def has_role(user, role, organization):
    try:
        return user.organization_memberships.filter(
            role=role, organization=organization
        ).exists()
    except:
        return False


@register.simple_tag
def get_is_admin(user, organization):
    try:
        return user.organization_memberships.filter(
            role="admin", organization=organization
        ).exists()
    except:
        return False
