from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils.timezone import now
from accounts.models import OrganizationMembership
from .models import DataUpload, Metric
from subscriptions.utils import (
    get_plan_limits, 
    can_upload_data, 
    can_view_more_reports, 
    can_download_pdf_reports,
    )
import boto3
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from weasyprint import HTML
from django.template.loader import render_to_string
from django.http import HttpResponse
import uuid
import mimetypes
import json
import logging


logger = logging.getLogger(__name__)


@login_required
def upload_data(request):
    user = request.user
    organization = (
        user.owned_organization
        if hasattr(user, "owned_organization") and user.owned_organization
        else user.organization_memberships.first().organization
    )

    limits = get_plan_limits(organization)
    if limits is None:
        messages.warning(request, "You need an active subscription to upload data.")
        return redirect("subscriptions:pricing")
    max_uploads = limits.get("max_uploads_per_month", 1)
    start_of_month = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    uploads_used = organization.data_uploads.filter(created_at__gte=start_of_month).count()

    return render(
        request,
        "dashboard/analytics/upload_data.html",
        {
            "USE_S3": settings.USE_S3,
            "uploads_used": uploads_used,
            "uploads_remaining": max(0, max_uploads - uploads_used),
            "max_uploads": max_uploads,
        },
    )


@login_required
@require_POST
def generate_presigned_post(request):
    logger.info("🔧 generate_presigned_post: Request received")

    file_name = request.POST.get("file_name")
    if not file_name:
        logger.warning("❌ Missing file name in POST")
        return JsonResponse({"error": "Missing file name"}, status=400)

    logger.info(f"📦 Requested file_name: {file_name}")
    mime_type, _ = mimetypes.guess_type(file_name)
    mime_type = mime_type or "application/octet-stream"
    logger.info(f"🧪 Guessed MIME type: {mime_type}")

    user = request.user
    organization = (
        user.owned_organization
        if hasattr(user, "owned_organization") and user.owned_organization
        else user.organization_memberships.first().organization
    )
    org_slug = organization.name.lower().replace(" ", "_")
    key = f"uploads/{org_slug}/data/{uuid.uuid4()}_{file_name.replace(' ', '_')}"
    logger.info(f"🗝️ Generated S3 key: {key}")

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
            Fields={},
            Conditions=[
                ["starts-with", "$key", f"uploads/{org_slug}/data/"],
                ["content-length-range", 0, settings.MAX_UPLOAD_SIZE_BYTES],
            ],
            ExpiresIn=3600
        )
        logger.info("✅ Presigned POST successfully generated")
        return JsonResponse({"data": presigned_post, "file_key": key})
    except Exception as e:
        logger.exception("🔥 Error generating presigned POST")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_POST
@login_required
def confirm_upload(request):
    logger.info("📥 confirm_upload: Metadata received")

    try:
        title = request.POST.get("title")
        job_instructions = request.POST.get("job_instructions")
        file_key = request.POST.get("file_key")

        if not title or not file_key:
            logger.warning("⚠️ Missing title or file_key in request")
            messages.error(request, "Missing required fields.")
            return JsonResponse({"redirect_url": "/dashboard/analytics/upload/"}, status=400)

        user = request.user
        organization = (
            user.owned_organization
            if hasattr(user, "owned_organization") and user.owned_organization
            else user.organization_memberships.first().organization
        )

        if not can_upload_data(organization):
            logger.warning(f"⛔ Upload limit reached for {organization.name}")
            messages.warning(request, "Upload limit reached for your current subscription plan.")
            return JsonResponse({"redirect_url": "/dashboard/analytics/upload/"}, status=403)

        DataUpload.objects.create(
            title=title,
            job_instructions=job_instructions,
            uploaded_by=user,
            organization=organization,
            file=file_key,
            status="uploaded"
        )

        logger.info(f"✅ Upload metadata saved and file marked as uploaded: {file_key}")
        return JsonResponse({"success": True})

    except Exception as e:
        logger.exception("❌ Error in confirm_upload")
        messages.error(request, "Something went wrong while confirming the upload.")
        return JsonResponse({"redirect_url": "/dashboard/analytics/upload/"}, status=500)

@csrf_exempt
@require_POST
@login_required
def initiate_multipart_upload(request):
    file_name = request.POST.get("file_name")
    mime_type = request.POST.get("content_type", "application/octet-stream")

    if not file_name:
        return JsonResponse({"error": "Missing file_name"}, status=400)

    user = request.user
    organization = (
        user.owned_organization
        if hasattr(user, "owned_organization") and user.owned_organization
        else user.organization_memberships.first().organization
    )
    org_slug = organization.name.lower().replace(" ", "_")
    key = f"uploads/{org_slug}/data/{uuid.uuid4()}_{file_name.replace(' ', '_')}"

    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
    )

    try:
        response = s3.create_multipart_upload(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=key,
            ContentType=mime_type,
        )
        return JsonResponse({"uploadId": response["UploadId"], "key": key})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_POST
@login_required
def generate_part_presigned_url(request):
    data = json.loads(request.body)
    key = data.get("key")
    upload_id = data.get("uploadId")
    part_number = data.get("partNumber")

    if not key or not upload_id or not part_number:
        return JsonResponse({"error": "Missing required parameters"}, status=400)

    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
    )

    try:
        url = s3.generate_presigned_url(
            "upload_part",
            Params={
                "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                "Key": key,
                "UploadId": upload_id,
                "PartNumber": part_number,
            },
            ExpiresIn=3600,
        )
        return JsonResponse({"url": url})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_POST
@login_required
def complete_multipart_upload(request):
    try:
        data = json.loads(request.body)
        upload_id = data.get("uploadId")
        key = data.get("key")
        parts = data.get("parts")
        title = data.get("title")
        job_instructions = data.get("job_instructions")

        if not upload_id or not key or not parts or not title:
            messages.error(request, "Missing required fields.")
            return JsonResponse({"redirect_url": "/dashboard/analytics/upload/"}, status=400)

        user = request.user
        organization = (
            user.owned_organization
            if hasattr(user, "owned_organization") and user.owned_organization
            else user.organization_memberships.first().organization
        )

        if not can_upload_data(organization):
            logger.warning(f"⛔ Upload limit reached (multipart) for {organization.name}")
            messages.warning(request, "Upload limit reached for your current subscription plan.")
            return JsonResponse({"redirect_url": "/dashboard/analytics/upload/"}, status=403)

        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )

        s3.complete_multipart_upload(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )

        DataUpload.objects.create(
            title=title,
            job_instructions=job_instructions,
            uploaded_by=user,
            organization=organization,
            file=key,
            status="uploaded"
        )

        logger.info("✅ Multipart upload completed and saved.")
        return JsonResponse({"success": True})

    except Exception as e:
        logger.exception("❌ Error during multipart upload completion")
        messages.error(request, "Error finalizing the upload.")
        return JsonResponse({"redirect_url": "/dashboard/analytics/upload/"}, status=500)


@login_required
def data_upload_list(request):
    user = request.user

    organization = (
        user.owned_organization
        if hasattr(user, "owned_organization") and user.owned_organization
        else user.organization_memberships.first().organization
    )

    if not organization:
        raise PermissionDenied("You are not part of any organization.")

    if not can_view_more_reports(organization):
        messages.warning(
            request,
            "You've reached the maximum number of processed reports allowed by your current plan."
        )

    data_uploads = (
        DataUpload.objects.filter(organization=organization, processed=True)
        .select_related("organization", "uploaded_by")
        .order_by("-created_at")
    )

    limits = get_plan_limits(organization)
    max_reports = limits.get("max_reports", 3) if limits else 3
    current_reports = organization.data_uploads.filter(processed=True).count()
    can_download_pdf = limits.get("allow_pdf_download", False) if limits else False

    return render(
        request,
        "dashboard/analytics/uploads_list.html",
        {
            "data_uploads": data_uploads,
            "can_download_pdf": can_download_pdf,
            "max_reports": max_reports,
            "current_reports": current_reports,
        },
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
    try:
        data_upload_presigned_url = data_upload.get_presigned_url()
    except Exception as e:
        data_upload_presigned_url = None

    for metric in metrics:
        metric.presigned_url = metric.get_presigned_url()

    # ✅ Check if the organization is allowed to download PDFs
    can_download_pdf = can_download_pdf_reports(organization)

    context = {
        "data_upload": data_upload,
        "data_upload_presigned_url": data_upload_presigned_url,
        "metrics": metrics,
        "can_download_pdf": can_download_pdf,  # ✅ Include in template context
    }
    return render(request, "dashboard/analytics/upload_detail.html", context)


@login_required
def download_pdf_report(request, upload_id):
    data_upload = get_object_or_404(DataUpload, id=upload_id, processed=True)

    organization = (
        request.user.owned_organization
        if hasattr(request.user, "owned_organization") and request.user.owned_organization
        else request.user.organization_memberships.first().organization
    )

    if not organization or data_upload.organization != organization:
        raise PermissionDenied("You do not have access to this report.")

    if not can_download_pdf_reports(organization):
        from django.contrib import messages
        messages.warning(request, "PDF downloads are only available on Business and Enterprise plans.")
        return redirect("analytics:data_upload_detail", upload_id=upload_id)

    metrics = Metric.objects.filter(datasource=data_upload).select_related("table_data")

    html = render_to_string(
        "dashboard/analytics/pdf_report.html",
        {"data_upload": data_upload, "metrics": metrics},
        request=request
    )

    pdf_file = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = f"inline; filename=Report_{data_upload.id}.pdf"
    return response