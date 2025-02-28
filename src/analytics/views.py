from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
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
