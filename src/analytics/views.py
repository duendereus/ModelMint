import logging
from django.contrib import messages
from django.shortcuts import render, redirect
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from analytics.utils import validate_file_extension
from analytics.models import DataUpload
from django.contrib.auth.decorators import login_required

import logging

logger = logging.getLogger(__name__)


@login_required
def upload_data(request):
    """Handles file uploads ensuring organization and user are auto-filled."""
    if request.method == "POST":
        title = request.POST.get("title", "")
        file = request.FILES.get("file")
        job_instructions = request.POST.get("job_instructions", "")
        user = request.user

        logger.info(f"📥 Received upload request from {user.email} with file: {file}")

        # ✅ Determine the organization for both owners and members
        organization = None
        if hasattr(user, "owned_organization") and user.owned_organization:
            organization = user.owned_organization
        else:
            membership = user.organization_memberships.first()
            if membership:
                organization = membership.organization

        if not organization:
            logger.error("❌ No organization found for user.")
            messages.error(
                request, "You must belong to an organization to upload data."
            )
            return redirect("dashboard:analytics:upload_data")

        # ✅ Attempt to save the file
        try:
            upload = DataUpload.objects.create(
                title=title,
                file=file,
                job_instructions=job_instructions,
                uploaded_by=user,
                organization=organization,
            )
            logger.info(f"✅ Upload successful: {upload.file.url}")
            messages.success(request, "File uploaded successfully!")
        except Exception as e:
            logger.error(f"❌ Upload failed: {str(e)}", exc_info=True)
            messages.error(request, "Upload failed. Please try again.")

        return redirect("dashboard:dashboard_home")

    return render(request, "dashboard/analytics/upload_data.html")
