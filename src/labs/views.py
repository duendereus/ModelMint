from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.models import Organization, OrganizationMembership


@login_required
def labs_enroll_view(request):
    """
    Allows an authenticated user to enroll in Labs by creating a 'lab' organization.
    """
    user = request.user

    # Prevenir que usuarios ya en una organización se inscriban a otra
    if hasattr(user, "owned_organization"):
        messages.info(request, "You already belong to an organization.")
        return redirect("dashboard:dashboard_home")

    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            org = Organization.objects.create(
                name=name,
                owner=user,
                type="lab",
            )
            OrganizationMembership.objects.create(
                organization=org,
                user=user,
                role="admin",
            )
            messages.success(request, "Your Lab has been created.")
            return redirect("labs:dashboard")
        else:
            messages.error(request, "Please provide a name for your Lab.")

    return render(request, "labs/accounts/labs_enroll.html")
