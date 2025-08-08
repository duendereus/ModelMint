from subscriptions.utils import get_plan_limits


def compute_branding_context(organization):
    """
    Devuelve el dict de branding para una organización *si su suscripción está activa*
    y el plan tiene branding habilitado. Si no, devuelve {}.
    """
    if not organization:
        return {}

    subscription = getattr(organization, "subscription", None)
    if not subscription or not subscription.is_active_status:
        return {}

    limits = get_plan_limits(organization)
    if limits.get("branding", "none") == "none":
        return {}

    profile = getattr(organization, "profile", None)

    return {
        "branding_enabled": True,
        "branding_level": limits.get("branding"),
        "org_logo": (profile.logo.url if (profile and profile.logo) else None),
        "primary_color": (profile.primary_color if profile else "#198754"),
        "secondary_color": (profile.secondary_color if profile else "#6c757d"),
        "text_color": (profile.text_color if profile else "#000000"),
        "background_color": (profile.background_color if profile else "#ffffff"),
        "org_tagline": (profile.tagline if profile else ""),
        "org_name": organization.name,
    }
