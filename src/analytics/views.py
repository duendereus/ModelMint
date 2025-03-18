from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from accounts.models import OrganizationMembership
from .models import DataUpload, Metric
from .tasks import save_uploaded_file


@login_required
def upload_data(request):
    """Handles file uploads ensuring organization and user are auto-filled asynchronously."""

    if request.method == "POST":
        title = request.POST.get("title", "")
        file = request.FILES.get("file")  # ✅ Pass the file directly to Django storage
        job_instructions = request.POST.get("job_instructions", "")
        user = request.user

        if not file:
            messages.error(request, "Please upload a valid file.")
            return redirect("dashboard:analytics:upload_data")

        # ✅ Identify organization
        organization = None
        if hasattr(user, "owned_organization") and user.owned_organization:
            organization = user.owned_organization
        else:
            membership = user.organization_memberships.first()
            if membership:
                organization = membership.organization

        if not organization:
            messages.error(
                request, "You must belong to an organization to upload files."
            )
            return redirect("dashboard:analytics:upload_data")

        # ✅ Save DataUpload instance (THIS SAVES THE FILE IN S3 or LOCAL STORAGE)
        data_upload = DataUpload.objects.create(
            title=title,
            job_instructions=job_instructions,
            uploaded_by=user,
            organization=organization,
            file=file,  # ✅ Directly save to FileField, no reading required
        )

        # ✅ Send task with only the DataUpload ID
        save_uploaded_file.delay(data_upload.id)

        messages.success(request, "Your file is being uploaded in the background!")
        return redirect("dashboard:dashboard_home")

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


@login_required
def data_upload_detail(request, upload_id):
    """
    Displays the details of a specific processed DataUpload, including its related Metrics.
    """
    user = request.user

    # Get the DataUpload object (raises 404 if not found)
    data_upload = get_object_or_404(DataUpload, id=upload_id, processed=True)

    # Determine the user's organization
    organization = None
    if hasattr(user, "owned_organization"):
        organization = user.owned_organization
    else:
        membership = user.organization_memberships.first()
        if membership:
            organization = membership.organization

    # Check if user has access to this DataUpload
    if not organization or data_upload.organization != organization:
        raise PermissionDenied("You do not have access to this data upload.")

    # Fetch related metrics and optimize queries
    metrics = (
        Metric.objects.filter(datasource=data_upload)
        .select_related("table_data")  # Includes TableMetric if exists
        .order_by("position")
    )

    # ✅ Generate pre-signed URLs for all files
    data_upload_presigned_url = data_upload.get_presigned_url()
    for metric in metrics:
        metric.presigned_url = metric.get_presigned_url()  # Add presigned_url to metric

    context = {
        "data_upload": data_upload,
        "data_upload_presigned_url": data_upload_presigned_url,  # ✅ Pass the pre-signed URL
        "metrics": metrics,
    }
    return render(request, "dashboard/analytics/upload_detail.html", context)
