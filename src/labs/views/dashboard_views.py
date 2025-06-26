from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from labs.models import LabNotebook


from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from accounts.models import OrganizationMembership
from accounts.decorators import labs_only
from labs.models import LabNotebook


@login_required
@labs_only
def dashboard_home_labs_view(request):
    """
    Labs Dashboard Home View:
    Muestra los LabNotebooks subidos por los miembros del equipo.
    Solo accesible si el usuario pertenece a una organización tipo 'lab'.
    """
    organization = None
    is_owner = False
    is_member = False
    notebooks = []

    # Detecta si es owner o miembro
    if (
        hasattr(request.user, "owned_organization")
        and request.user.owned_organization.type == "lab"
    ):
        organization = request.user.owned_organization
        is_owner = True
    else:
        membership = OrganizationMembership.objects.filter(
            user=request.user, organization__type="lab"
        ).first()
        if membership:
            organization = membership.organization
            is_member = True

    if organization:
        notebooks = LabNotebook.objects.filter(organization=organization).order_by(
            "-created_at"
        )

    return render(
        request,
        "labs/dashboard/home.html",
        {
            "organization": organization,
            "is_owner": is_owner,
            "is_member": is_member,
            "notebooks": notebooks,
        },
    )
