from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils.timezone import now
from .models import DataSet, DataUpload, Metric
from .forms import DataUploadForm
from subscriptions.utils import (
    get_plan_limits,
    can_upload_data,
    can_view_more_reports,
    can_download_pdf_reports,
)
import boto3
from django.views.decorators.http import require_POST
from django.http import JsonResponse, Http404
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

try:
    from weasyprint import HTML
except ImportError:
    HTML = None
from django.template.loader import render_to_string
from django.http import HttpResponse
import uuid
import mimetypes
import json
import logging
from django.db.models import Prefetch, Q
from config.decorators import staff_required
from accounts.models import Organization


logger = logging.getLogger(__name__)


@login_required
def upload_data(request):
    user = request.user
    organization = getattr(user, "owned_organization", None)
    if not organization:
        membership = user.organization_memberships.first()
        organization = membership.organization if membership else None

    if not organization:
        messages.error(request, "You must belong to an organization to upload data.")
        return redirect("dashboard:dashboard_home")

    limits = get_plan_limits(organization)
    if limits is None:
        messages.warning(request, "You need an active subscription to upload data.")
        return redirect("subscriptions:pricing")

    max_uploads = limits.get("max_uploads_per_month", 1)
    start_of_month = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    uploads_used = organization.data_uploads.filter(
        created_at__gte=start_of_month
    ).count()

    datasets = DataSet.objects.filter(organization=organization).order_by("name")
    form = DataUploadForm()

    return render(
        request,
        "dashboard/analytics/upload_data.html",
        {
            "form": form,
            "uploads_used": uploads_used,
            "uploads_remaining": max(0, max_uploads - uploads_used),
            "max_uploads": max_uploads,
            "datasets": datasets,
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

    user = request.user
    organization = (
        user.owned_organization
        if hasattr(user, "owned_organization") and user.owned_organization
        else user.organization_memberships.first().organization
    )
    org_slug = organization.name.lower().replace(" ", "_")
    key = f"uploads/{org_slug}/data/{uuid.uuid4()}_{file_name.replace(' ', '_')}"

    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )

        logger.info("After s3_client")
        # presigned_post = s3_client.generate_presigned_post(
        #     Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        #     Key=key,
        #     Fields={
        #         "Content-Type": mime_type,
        #     },
        #     Conditions=[
        #         {"Content-Type": mime_type},
        #         ["starts-with", "$key", f"uploads/{org_slug}/data/"],
        #         ["content-length-range", 0, settings.MAX_UPLOAD_SIZE_BYTES],
        #     ],
        #     ExpiresIn=3600,
        # )
        presigned_post = s3_client.generate_presigned_post(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=key,
            Conditions=[
                ["starts-with", "$key", f"uploads/{org_slug}/data/"],
                ["content-length-range", 0, settings.MAX_UPLOAD_SIZE_BYTES],
            ],
            ExpiresIn=3600,
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
        drive_link = request.POST.get("drive_link")
        operation = request.POST.get("operation", "create")

        if not title or (not file_key and not drive_link) or not operation:
            logger.warning("⚠️ Missing basic required fields")
            return JsonResponse({"error": "Missing basic required fields."}, status=400)

        # Extra validation for "create"
        if operation == "create":
            dataset_name = request.POST.get("dataset_name")
            if not dataset_name:
                logger.warning("⚠️ Missing dataset name for 'create'")
                return JsonResponse({"error": "Missing dataset name."}, status=400)
        else:
            dataset_id = request.POST.get("dataset_id")
            if not dataset_id:
                logger.warning("⚠️ Missing dataset ID for append/replace")
                return JsonResponse({"error": "Missing dataset ID."}, status=400)

        user = request.user
        organization = (
            user.owned_organization
            if hasattr(user, "owned_organization") and user.owned_organization
            else user.organization_memberships.first().organization
        )

        if not can_upload_data(organization):
            logger.warning(f"⛔ Upload limit reached for {organization.name}")
            messages.warning(
                request, "Upload limit reached for your current subscription plan."
            )
            return JsonResponse(
                {"redirect_url": "/dashboard/analytics/upload/"}, status=403
            )

        # Handle dataset
        if operation == "create":
            dataset = DataSet.objects.create(
                name=dataset_name,
                organization=organization,
                created_by=user,
                description=request.POST.get("dataset_description", ""),
            )
        else:
            dataset = get_object_or_404(
                DataSet, id=dataset_id, organization=organization
            )

            if operation == "replace":
                dataset.uploads.update(removed=True)

        # Create the DataUpload (version is auto-handled in save())
        DataUpload.objects.create(
            title=title,
            job_instructions=job_instructions,
            uploaded_by=user,
            organization=organization,
            file=file_key if file_key else None,
            drive_link=drive_link if drive_link else None,
            status="uploaded",
            dataset=dataset,
            operation=operation,
        )

        logger.info(f"✅ Upload metadata saved and file marked as uploaded: {file_key}")
        return JsonResponse({"success": True})

    except Exception as e:
        logger.exception("❌ Error in confirm_upload")
        messages.error(request, "Something went wrong while confirming the upload.")
        return JsonResponse(
            {"redirect_url": "/dashboard/analytics/upload/"}, status=500
        )


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
        drive_link = data.get("drive_link")
        parts = data.get("parts")
        title = data.get("title")
        job_instructions = data.get("job_instructions")
        dataset_name = data.get("dataset_name")
        operation = data.get("operation", "create")

        if not upload_id or not key or not parts or not title or not dataset_name:
            messages.error(request, "Missing required fields.")
            return JsonResponse(
                {"redirect_url": "/dashboard/analytics/upload/"}, status=400
            )

        user = request.user
        organization = (
            user.owned_organization
            if hasattr(user, "owned_organization") and user.owned_organization
            else user.organization_memberships.first().organization
        )

        if not can_upload_data(organization):
            logger.warning(
                f"⛔ Upload limit reached (multipart) for {organization.name}"
            )
            messages.warning(
                request, "Upload limit reached for your current subscription plan."
            )
            return JsonResponse(
                {"redirect_url": "/dashboard/analytics/upload/"}, status=403
            )

        # Finalize the multipart upload with S3
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

        # Handle dataset
        if operation == "create":
            dataset_name = data.get("dataset_name")
            if not dataset_name:
                return JsonResponse({"error": "Missing dataset name."}, status=400)

            dataset = DataSet.objects.create(
                name=dataset_name,
                organization=organization,
                created_by=user,
                description=data.get("dataset_description", ""),
            )
        else:
            dataset_id = data.get("dataset_id")
            if not dataset_id:
                return JsonResponse(
                    {"error": "Missing dataset ID for append/replace."}, status=400
                )

            dataset = get_object_or_404(
                DataSet, id=dataset_id, organization=organization
            )

            if operation == "replace":
                dataset.uploads.update(removed=True)

        # Save the upload
        DataUpload.objects.create(
            title=title,
            job_instructions=job_instructions,
            uploaded_by=user,
            organization=organization,
            file=key if key else None,
            drive_link=drive_link if drive_link else None,
            status="uploaded",
            dataset=dataset,
            operation=operation,
        )

        logger.info("✅ Multipart upload completed and saved.")
        return JsonResponse({"success": True})

    except Exception as e:
        logger.exception("❌ Error during multipart upload completion")
        messages.error(request, "Error finalizing the upload.")
        return JsonResponse(
            {"redirect_url": "/dashboard/analytics/upload/"}, status=500
        )


@login_required
def report_list_view(request):
    user = request.user

    organization = (
        user.owned_organization
        if hasattr(user, "owned_organization") and user.owned_organization
        else (
            user.organization_memberships.first().organization
            if user.organization_memberships.exists()
            else None
        )
    )

    if not organization:
        messages.warning(request, "You must belong to an organization to view reports.")
        return redirect("dashboard:dashboard_home")  # o donde tú prefieras

    if not can_view_more_reports(organization):
        messages.warning(
            request,
            "You've reached the maximum number of processed reports allowed by your current plan.",
        )

    datasets = (
        DataSet.objects.filter(organization=organization)
        .prefetch_related(
            Prefetch(
                "uploads",
                queryset=DataUpload.objects.filter(used_for_processing=True).order_by(
                    "-version"
                ),
                to_attr="processed_uploads",
            )
        )
        .order_by("name")
    )

    limits = get_plan_limits(organization)
    max_reports = limits.get("max_reports") if limits else 0
    is_unlimited = max_reports == float("inf")
    current_reports = DataUpload.objects.filter(
        organization=organization, used_for_processing=True
    ).count()
    can_download_pdf = limits.get("allow_pdf_download", False) if limits else False

    return render(
        request,
        "dashboard/analytics/report_list.html",
        {
            "datasets": datasets,
            "can_download_pdf": can_download_pdf,
            "max_reports": max_reports,
            "current_reports": current_reports,
            "is_unlimited": is_unlimited,
        },
    )


@login_required
def report_detail_view(request, dataset_id):
    """
    Shows the latest processed DataUpload for a given DataSet
    and its associated Metrics.
    """
    user = request.user

    organization = (
        user.owned_organization
        if hasattr(user, "owned_organization") and user.owned_organization
        else (
            user.organization_memberships.first().organization
            if user.organization_memberships.exists()
            else None
        )
    )

    if not organization:
        messages.warning(
            request, "You must belong to an organization to view this report."
        )
        return redirect("dashboard:dashboard_home")  # o donde prefieras

    dataset = get_object_or_404(DataSet, id=dataset_id, organization=organization)

    latest_upload = (
        dataset.uploads.filter(used_for_processing=True)
        .order_by("-version", "-created_at")
        .first()
    )

    if not latest_upload:
        raise Http404("No processed data upload available for this dataset.")

    # metrics = (
    #     Metric.objects.filter(dataset=dataset)
    #     .select_related("table_data")
    #     .order_by("position")
    # )
    metrics = (
        Metric.objects.filter(dataset=dataset)
        .filter(Q(source_upload=latest_upload) | Q(source_upload__isnull=True))
        .select_related("table_data")
        .order_by("position")
    )

    try:
        data_upload_presigned_url = latest_upload.get_presigned_url()
    except Exception:
        data_upload_presigned_url = None

    for metric in metrics:
        metric.presigned_url = metric.get_presigned_url()

    can_download_pdf = can_download_pdf_reports(organization)

    return render(
        request,
        "dashboard/analytics/report_detail.html",
        {
            "data_upload": latest_upload,
            "metrics": metrics,
            "can_download_pdf": can_download_pdf,
            "data_upload_presigned_url": data_upload_presigned_url,
        },
    )


@login_required
def download_pdf_report(request, upload_id):
    try:
        data_upload = get_object_or_404(
            DataUpload, id=upload_id, used_for_processing=True
        )

        user = request.user
        organization = (
            user.owned_organization
            if hasattr(user, "owned_organization") and user.owned_organization
            else user.organization_memberships.first().organization
        )

        if not organization or data_upload.organization != organization:
            raise PermissionDenied("You do not have access to this report.")

        if not can_download_pdf_reports(organization):
            messages.warning(
                request,
                "PDF downloads are only available on Business and Enterprise plans.",
            )
            return redirect(
                "dashboard:analytics:report_detail_view",
                dataset_id=data_upload.dataset.id,
            )

        metrics = Metric.objects.filter(dataset=data_upload.dataset).select_related(
            "table_data"
        )

        # ✅ Attach presigned URL for plots
        for metric in metrics:
            if metric.file:
                metric.presigned_url = metric.get_presigned_url()
            else:
                metric.presigned_url = None

        html = render_to_string(
            "dashboard/analytics/pdf_report.html",
            {"data_upload": data_upload, "metrics": metrics},
            request=request,
        )

        pdf_file = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()

        response = HttpResponse(pdf_file, content_type="application/pdf")
        response["Content-Disposition"] = (
            f"inline; filename=Report_{data_upload.id}.pdf"
        )
        return response

    except Exception:
        return HttpResponse(
            "An error occurred while generating the PDF. Please try again later.",
            status=500,
        )


@login_required
def get_available_datasets(request):
    """
    Return a list of versioned datasets available to the user's organization.
    Only used for 'append' and 'replace' uploads.
    """
    user = request.user
    organization = (
        user.owned_organization
        if hasattr(user, "owned_organization") and user.owned_organization
        else user.organization_memberships.first().organization
    )

    datasets = (
        DataSet.objects.filter(organization=organization)
        .order_by("name")
        .values("id", "name")
    )

    return JsonResponse({"datasets": list(datasets)})


@staff_required
def staff_dataset_list_view(request):
    """
    Shows all datasets grouped by organization for staff users.
    """
    organizations = Organization.objects.prefetch_related(
        Prefetch(
            "datasets",
            queryset=DataSet.objects.prefetch_related("uploads").order_by("name"),
            to_attr="annotated_datasets",
        )
    ).order_by("name")

    for org in organizations:
        sub_obj = getattr(org, "subscription", None)  # Safe access
        if sub_obj and sub_obj.subscription:
            plan_name = sub_obj.subscription.name.lower()
            org.subscription_label = sub_obj.subscription.name
            org.subscription_status = sub_obj.status or "unknown"

            if "enterprise" in plan_name:
                org.subscription_color = "bg-success"
            elif "business" in plan_name:
                org.subscription_color = "bg-primary"
            elif "starter" in plan_name:
                org.subscription_color = "bg-secondary"
            else:
                org.subscription_color = "bg-dark"

            # Status visual
            if sub_obj.status == "active":
                org.status_class = "badge bg-success"
                org.status_icon = "mdi-check-circle"
            elif sub_obj.status == "trialing":
                org.status_class = "badge bg-info text-dark"
                org.status_icon = "mdi-timer-sand"
            elif sub_obj.status == "past_due":
                org.status_class = "badge bg-warning text-dark"
                org.status_icon = "mdi-alert-circle"
            elif sub_obj.status == "canceled":
                org.status_class = "badge bg-danger"
                org.status_icon = "mdi-close-circle"
            elif sub_obj.status == "paused":
                org.status_class = "badge bg-secondary"
                org.status_icon = "mdi-pause-circle"
            else:
                org.status_class = "badge bg-dark"
                org.status_icon = "mdi-help-circle"

        else:
            org.subscription_label = "No Plan"
            org.subscription_color = "bg-dark"
            org.subscription_status = "NA"
            org.status_class = "badge bg-dark"
            org.status_icon = "mdi-help-circle"

    return render(
        request,
        "dashboard/admin/staff_dataset_list.html",
        {"organizations": organizations},
    )


@staff_required
@require_POST
def mark_dataset_as_processed(request, dataset_id):
    dataset = get_object_or_404(DataSet, id=dataset_id)
    dataset.processed = True
    dataset.save()
    return JsonResponse(
        {"success": True, "message": f"Dataset '{dataset.name}' marked as processed."}
    )
