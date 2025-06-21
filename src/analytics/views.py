from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils.timezone import now
from .models import DataSet, DataUpload, Report, Metric, JupyterReport
from .forms import DataUploadForm, ReportRequestForm
from .tasks import process_metrics_task
from .services import mark_as_processed
from analytics.utils.utils import get_user_organization
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
from django.views.decorators.http import require_http_methods

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
import os
from django.db.models import Prefetch, Q
from config.decorators import staff_required
from accounts.models import Organization
from django.core.files.storage import default_storage
import base64
import requests


logger = logging.getLogger(__name__)


@login_required
def upload_data(request):
    user = request.user
    organization = get_user_organization(user)

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
def request_report_view(request):
    user = request.user
    organization = get_user_organization(user)

    if not organization:
        messages.error(
            request, "You must belong to an organization to request a report."
        )
        return redirect("dashboard:dashboard_home")

    # ❗️Verifica que tenga datasets disponibles
    datasets = DataSet.objects.filter(organization=organization)
    if not datasets.exists():
        messages.warning(request, "You must first upload data to create a report.")
        return redirect("dashboard:analytics:upload_data")

    # ✅ Verifica límites del plan
    limits = get_plan_limits(organization)
    if limits is None:
        messages.warning(
            request, "You need an active subscription to request a report."
        )
        return redirect("subscriptions:pricing")

    max_reports = limits.get("max_reports", 3)
    processed_reports_count = Report.objects.filter(
        dataset__organization=organization, processed=True
    ).count()

    if processed_reports_count >= max_reports:
        messages.warning(
            request,
            f"You've reached the report limit ({max_reports}) for your current plan. Upgrade to generate more reports.",
        )
        return redirect("dashboard:dashboard_home")

    if request.method == "POST":
        form = ReportRequestForm(request.POST, organization=organization)
        if form.is_valid():
            report = form.save(commit=False)
            report.created_by = user
            report.save()
            messages.success(request, "✅ Report request submitted.")
            return redirect("dashboard:dashboard_home")
    else:
        form = ReportRequestForm(organization=organization)

    return render(
        request,
        "dashboard/analytics/request_report.html",
        {
            "form": form,
            "max_reports": max_reports if max_reports != float("inf") else None,
            "processed_reports_count": processed_reports_count,
            "reports_remaining": (
                max_reports - processed_reports_count
                if max_reports != float("inf")
                else None
            ),
            "unlimited_reports": max_reports == float("inf"),
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
    organization = get_user_organization(user)
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
        file_key = request.POST.get("file_key")
        drive_link = request.POST.get("drive_link")
        operation = request.POST.get("operation", "create")

        if (not file_key and not drive_link) or not operation:
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
        organization = get_user_organization(user)

        if not can_upload_data(organization):
            logger.warning(f"⛔ Upload limit reached for {organization.name}")
            messages.warning(
                request, "Upload limit reached for your current subscription plan."
            )
            return JsonResponse(
                {"redirect_url": reverse("dashboard:analytics:upload_data")}, status=403
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
            uploaded_by=user,
            organization=organization,
            file=file_key if file_key else None,
            drive_link=drive_link if drive_link else None,
            status="uploaded",
            dataset=dataset,
            operation=operation,
        )

        logger.info(f"✅ Upload metadata saved and file marked as uploaded: {file_key}")
        return JsonResponse(
            {
                "success": True,
                "redirect_url": reverse("dashboard:analytics:request_report"),
            }
        )

    except Exception as e:
        logger.exception("❌ Error in confirm_upload")
        messages.error(request, "Something went wrong while confirming the upload.")
        return JsonResponse(
            {"redirect_url": reverse("dashboard:analytics:upload_data")}, status=500
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
    organization = get_user_organization(user)
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
        dataset_name = data.get("dataset_name")
        operation = data.get("operation", "create")

        if not upload_id or not key or not parts or not dataset_name:
            messages.error(request, "Missing required fields.")
            return JsonResponse(
                {"redirect_url": reverse("dashboard:analytics:upload_data")}, status=400
            )

        user = request.user
        organization = get_user_organization(user)

        if not can_upload_data(organization):
            logger.warning(
                f"⛔ Upload limit reached (multipart) for {organization.name}"
            )
            messages.warning(
                request, "Upload limit reached for your current subscription plan."
            )
            return JsonResponse(
                {"redirect_url": reverse("dashboard:analytics:upload_data")}, status=403
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
            uploaded_by=user,
            organization=organization,
            file=key if key else None,
            drive_link=drive_link if drive_link else None,
            status="uploaded",
            dataset=dataset,
            operation=operation,
        )

        logger.info("✅ Multipart upload completed and saved.")
        return JsonResponse(
            {
                "success": True,
                "redirect_url": reverse("dashboard:analytics:request_report"),
            }
        )

    except Exception as e:
        logger.exception("❌ Error during multipart upload completion")
        messages.error(request, "Error finalizing the upload.")
        return JsonResponse(
            {"redirect_url": reverse("dashboard:analytics:upload_data")}, status=500
        )


@login_required
def report_list_view(request):
    user = request.user

    organization = get_user_organization(user)

    if not organization:
        messages.warning(request, "You must belong to an organization to view reports.")
        return redirect("dashboard:dashboard_home")

    if not can_view_more_reports(organization):
        messages.warning(
            request,
            (
                "You've reached the maximum number of processed "
                "reports allowed by your current plan."
            ),
        )

    datasets = (
        DataSet.objects.filter(organization=organization)
        .prefetch_related("reports__upload")
        .order_by("name")
    )

    limits = get_plan_limits(organization)
    max_reports = limits.get("max_reports") if limits else 0
    is_unlimited = max_reports == float("inf")
    current_reports = Report.objects.filter(
        dataset__organization=organization, processed=True
    ).count()
    can_download_pdf = limits.get("allow_pdf_download", False) if limits else False

    return render(
        request,
        "dashboard/analytics/report_list.html",
        {
            "datasets": datasets,
            "is_unlimited": is_unlimited,
            "current_reports": current_reports,
            "max_reports": max_reports,
            "can_download_pdf": can_download_pdf,
        },
    )


@login_required
def report_detail_view(request, report_id):
    """
    Shows the details of a processed Report and its associated Metrics.
    """
    user = request.user
    organization = get_user_organization(user)

    if not organization:
        messages.warning(
            request, "You must belong to an organization to view this report."
        )
        return redirect("dashboard:dashboard_home")

    report = get_object_or_404(
        Report.objects.select_related("dataset", "upload").prefetch_related(
            "metrics__table_data"
        ),
        id=report_id,
        processed=True,
        dataset__organization=organization,
    )

    data_upload = report.upload
    try:
        data_upload_presigned_url = (
            data_upload.get_presigned_url() if data_upload else None
        )
    except Exception:
        data_upload_presigned_url = None

    metrics = (
        report.metrics.filter(is_preview=False)
        .select_related("table_data")
        .order_by("position")
    )

    for metric in metrics:
        metric.presigned_url = metric.get_presigned_url()

    can_download_pdf = can_download_pdf_reports(organization)

    return render(
        request,
        "dashboard/analytics/report_detail.html",
        {
            "data_upload": data_upload,
            "report": report,
            "metrics": metrics,
            "can_download_pdf": can_download_pdf,
            "data_upload_presigned_url": data_upload_presigned_url,
        },
    )


@login_required
def download_pdf_report(request, report_id):
    try:
        report = get_object_or_404(Report, id=report_id, processed=True)
        dataset = report.dataset
        upload = report.upload

        user = request.user
        organization = get_user_organization(user)

        if not organization or dataset.organization != organization:
            raise PermissionDenied("You do not have access to this report.")

        if not can_download_pdf_reports(organization):
            messages.warning(
                request,
                "PDF downloads are only available on Business and Enterprise plans.",
            )
            return redirect(
                "dashboard:analytics:report_detail_view",
                report_id=report.id,
            )

        # ✅ Convertir logo a base64
        logo_base64 = None
        logo_path = os.path.join(settings.BASE_DIR, "static", "img", "logo-green.png")
        try:
            with open(logo_path, "rb") as logo_file:
                encoded_logo = base64.b64encode(logo_file.read()).decode()
                logo_base64 = f"data:image/png;base64,{encoded_logo}"
        except Exception:
            logo_base64 = None

        # ✅ Obtener métricas del Report
        metrics = (
            report.metrics.filter(is_preview=False)
            .select_related("table_data")
            .order_by("position")
        )

        for metric in metrics:
            metric.presigned_url = None
            metric.base64_image = None

            if metric.type == "plot" and metric.file:
                try:
                    presigned_url = metric.get_presigned_url(expires_in=60)
                    metric.presigned_url = presigned_url
                    response = requests.get(presigned_url)
                    response.raise_for_status()

                    encoded = base64.b64encode(response.content).decode()
                    ext = metric.file.name.split(".")[-1].lower()
                    ext = "png" if ext not in ["jpg", "jpeg", "svg"] else ext
                    metric.base64_image = f"data:image/{ext};base64,{encoded}"
                except Exception:
                    metric.base64_image = None

        # ✅ Render HTML y generar PDF
        html = render_to_string(
            "dashboard/analytics/pdf_report.html",
            {
                "report": report,
                "data_upload": upload,
                "metrics": metrics,
                "logo_base64": logo_base64,
            },
            request=request,
        )

        pdf_file = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()

        response = HttpResponse(pdf_file, content_type="application/pdf")
        response["Content-Disposition"] = f"inline; filename=Report_{report.id}.pdf"
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
    organization = get_user_organization(user)

    datasets = (
        DataSet.objects.filter(organization=organization)
        .order_by("name")
        .values("id", "name")
    )

    return JsonResponse({"datasets": list(datasets)})


@staff_required
def staff_dataset_list_view(request):
    """
    Shows all datasets and their reports grouped by organization for staff users.
    """
    organizations = Organization.objects.prefetch_related(
        Prefetch(
            "datasets",
            queryset=DataSet.objects.prefetch_related(
                Prefetch(
                    "uploads",
                    queryset=DataUpload.objects.select_related(
                        "dataset", "uploaded_by", "organization"
                    ).order_by("-version"),
                    to_attr="annotated_uploads",
                ),
                Prefetch(
                    "reports",
                    queryset=Report.objects.select_related("upload").order_by(
                        "-created_at"
                    ),
                    to_attr="annotated_reports",
                ),
            ).order_by("name"),
            to_attr="annotated_datasets",
        )
    ).order_by("name")

    for org in organizations:
        sub_obj = getattr(org, "subscription", None)
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


@staff_required
@require_http_methods(["GET", "POST"])
def staff_process_upload_view(request, upload_id):
    upload = get_object_or_404(
        DataUpload.objects.select_related("dataset__organization", "uploaded_by"),
        id=upload_id,
    )
    dataset = upload.dataset

    if request.method == "POST":
        html_file = request.FILES.get("jupyter_html")
        files = request.FILES.getlist("files")

        if not html_file:
            messages.error(request, "Jupyter HTML file is required.")
            return redirect(request.path)

        # 🧾 Crear Report y JupyterReport vinculados
        report = Report.objects.create(
            dataset=dataset,
            upload=upload,
            created_by=upload.uploaded_by,
            title="Reporte generado desde notebook",
        )

        # Después (✅)
        JupyterReport.objects.create(
            upload=upload,
            file=html_file,
            report=report,
        )

        # 📂 Guardar archivos complementarios temporalmente
        VALID_TABLE_EXTENSIONS = {".csv", ".xls", ".xlsx"}
        complementary_info = []

        for f in files:
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in VALID_TABLE_EXTENSIONS:
                messages.warning(request, f"⚠️ Skipped unsupported file: {f.name}")
                continue

            safe_name = f"{uuid.uuid4().hex}_{f.name.replace(' ', '_')}"
            stored_path = default_storage.save(f"metrics_temp/{safe_name}", f)

            complementary_info.append(
                {"stored_path": stored_path, "original_name": f.name}
            )

        # 🚀 Lanza tarea de Celery con report_id
        process_metrics_task.delay(
            report_id=report.id,
            file_entries=complementary_info,
        )

        mark_as_processed(report)

        messages.success(
            request,
            "📤 Upload received. Processing will complete in background.",
        )
        return redirect("dashboard:analytics:staff_dataset_list")

    return render(
        request,
        "dashboard/admin/staff_process_upload.html",
        {"upload": upload, "dataset": dataset},
    )


@staff_required
@require_http_methods(["GET", "POST"])
def staff_preview_report_view(request, report_id):
    report = get_object_or_404(
        Report.objects.select_related("dataset", "upload", "created_by"),
        id=report_id,
    )
    dataset = report.dataset
    upload = report.upload  # Puede ser None

    # ✅ Procesar POST para guardar orden, ediciones, etc.
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            ordered_ids = data.get("ordered_ids", [])
            removed_ids = data.get("removed_ids", [])
            edited_titles = data.get("edited_titles", {})
            edited_values = data.get("edited_values", {})

            if not ordered_ids:
                return JsonResponse(
                    {"success": False, "error": "Missing metric order."}, status=400
                )

            # Eliminar métricas
            if removed_ids:
                Metric.objects.filter(id__in=removed_ids, report=report).delete()

            TEMP_OFFSET = 10000
            for i, metric_id in enumerate(ordered_ids):
                Metric.objects.filter(id=metric_id, report=report).update(
                    position=TEMP_OFFSET + i
                )

            # Editar contenido
            for metric_id in set(edited_titles.keys()) | set(edited_values.keys()):
                try:
                    metric = Metric.objects.get(id=metric_id, report=report)
                    if metric.is_preview:
                        if metric_id in edited_titles:
                            metric.name = edited_titles[metric_id].strip()
                        if metric_id in edited_values and metric.type in [
                            "text",
                            "single_value",
                        ]:
                            metric.value = edited_values[metric_id].strip()
                        metric.save()
                except Metric.DoesNotExist:
                    continue

            # Reasignar posiciones limpias
            for final_position, metric_id in enumerate(ordered_ids):
                Metric.objects.filter(id=metric_id, report=report).update(
                    position=final_position
                )

            # Marcar como procesado
            report.processed = True
            report.save()
            Metric.objects.filter(report=report).update(is_preview=False)

            return JsonResponse(
                {
                    "success": True,
                    "redirect_url": reverse(
                        "dashboard:analytics:staff_preview_report_by_report",
                        args=[report.id],
                    ),
                }
            )

        except Exception as e:
            logger.exception("Error publishing report")
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    # 🔁 GET
    metrics = (
        Metric.objects.filter(report=report)
        .order_by("position")
        .select_related("table_data")
    )
    for m in metrics:
        m.presigned_url = m.get_presigned_url()

    # Mostrar cualquier JupyterReport ligado por `report`
    jupyter_reports = JupyterReport.objects.filter(report=report)

    return render(
        request,
        "dashboard/admin/staff_preview_report.html",
        {
            "upload": upload,  # puede ser None
            "dataset": dataset,
            "report": report,
            "metrics": metrics,
            "jupyter_reports": jupyter_reports,
        },
    )
