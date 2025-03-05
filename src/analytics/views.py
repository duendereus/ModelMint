from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from accounts.models import OrganizationMembership
from .models import DataUpload


@login_required
def upload_data(request):
    """Handles file uploads ensuring organization and user are auto-filled."""

    if request.method == "POST":
        title = request.POST.get("title", "")
        file = request.FILES.get("file")
        job_instructions = request.POST.get("job_instructions", "")

        user = request.user

        # ✅ Determine the organization for both owners and members
        organization = None
        if hasattr(user, "owned_organization") and user.owned_organization:
            organization = user.owned_organization
        else:
            # 🔥 Get the organization from the first membership (assuming 1 user -> 1 org)
            membership = user.organization_memberships.first()
            if membership:
                organization = membership.organization

        if not organization:
            messages.error(
                request, "You must belong to an organization to upload data."
            )
            return redirect(
                "dashboard:analytics:upload_data"
            )  # Redirect to prevent further errors

        # ✅ Save the data directly to the database
        upload = DataUpload.objects.create(
            title=title,
            file=file,
            job_instructions=job_instructions,
            uploaded_by=user,
            organization=organization,
        )
        print(upload)

        messages.success(request, "File uploaded successfully!")
        return redirect("dashboard:dashboard_home")  # Redirect after successful upload

    return render(request, "dashboard/analytics/upload_data.html")


@login_required
def data_upload_list(request):
    """
    Displays a list of processed DataUploads that the authenticated user has access to.
    The user must be either:
    1. The owner of an organization.
    2. A member of an organization.
    """
    user = request.user

    # Determine the organization
    organization = None

    if hasattr(user, "owned_organization"):
        # ✅ User is the **organization owner**
        organization = user.owned_organization
    else:
        # ✅ User is a **member of an organization**
        membership = OrganizationMembership.objects.filter(user=user).first()
        if membership:
            organization = membership.organization

    if not organization:
        # ❌ User does not belong to any organization → Deny access
        raise PermissionDenied("You are not part of any organization.")

    # ✅ Fetch only `processed=True` DataUploads for the user's organization
    data_uploads = (
        DataUpload.objects.filter(organization=organization, processed=True)
        .select_related("organization", "uploaded_by")
        .order_by("-created_at")
    )

    # Render template with the list
    return render(
        request, "dashboard/analytics/uploads_list.html", {"data_uploads": data_uploads}
    )
