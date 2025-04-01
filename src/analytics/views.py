from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from accounts.models import OrganizationMembership
from .models import DataUpload, Metric
# from .tasks import upload_to_s3_via_presigned_url
import boto3
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import uuid
import mimetypes
import logging

logger = logging.getLogger(__name__)


@login_required
def upload_data(request):
    return render(request, "dashboard/analytics/upload_data.html", {"USE_S3": settings.USE_S3})

@login_required
@require_POST
def generate_presigned_post(request):
    import mimetypes
    import boto3
    import uuid
    from django.conf import settings

    user = request.user
    organization = (
        user.owned_organization
        if hasattr(user, "owned_organization") and user.owned_organization
        else user.organization_memberships.first().organization
    )

    file_name = request.POST.get("file_name")
    if not file_name:
        return JsonResponse({"error": "Missing file name"}, status=400)

    mime_type, _ = mimetypes.guess_type(file_name)
    mime_type = mime_type or "application/octet-stream"

    org_slug = organization.name.lower().replace(" ", "_")
    key = f"uploads/{org_slug}/data/{uuid.uuid4()}_{file_name}"

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
    )

    try:
        presigned_post = s3_client.generate_presigned_post(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=key,
            Fields={"Content-Type": mime_type},
            Conditions=[{"Content-Type": mime_type}],
            ExpiresIn=3600
        )
        return JsonResponse({"data": presigned_post, "file_key": key})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_POST
@login_required
def confirm_upload(request):
    logger.info("📥 confirm_upload: Metadata POST received")

    title = request.POST.get("title")
    job_instructions = request.POST.get("job_instructions")
    file_key = request.POST.get("file_key")

    logger.info(f"📥 file_key: {file_key}, title: {title}")

    if not file_key or not title:
        logger.warning("⚠️ Missing title or file_key in confirm_upload")
        return JsonResponse({"error": "Missing file or title"}, status=400)

    user = request.user
    organization = (
        user.owned_organization
        if hasattr(user, "owned_organization") and user.owned_organization
        else user.organization_memberships.first().organization
    )

    DataUpload.objects.create(
        title=title,
        job_instructions=job_instructions,
        uploaded_by=user,
        organization=organization,
        file=file_key,
        status="uploaded"
    )

    logger.info(f"✅ Upload confirmed and DataUpload record created for: {file_key}")
    return JsonResponse({"success": True})


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
