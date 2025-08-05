from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from analytics.models import Metric, Report, DataUpload, DynamicDashboardConfig
from analytics.utils.process_jupyter_metrics import process_jupyter_metrics
from analytics.utils.jupyter_parser import clean_metric_name
from analytics.utils.generate_dashboard_config import (
    generate_dashboard_config,
    validate_dashboard_config,
)
from django.core.files.storage import default_storage
from django.template.loader import render_to_string
import os, uuid
import pandas as pd


@shared_task
def test_task():
    return "Celery is working!"


@shared_task
def process_metrics_task(report_id, upload_id=None, file_entries=None):
    """
    Procesa métricas del HTML + archivos complementarios usando los JupyterReport asociados.
    `file_entries`: lista de diccionarios con:
        - stored_path: ubicación del archivo guardado en storage (S3 o local)
        - original_name: nombre original del archivo (para usar como nombre de métrica)
    """
    try:
        report = Report.objects.get(id=report_id)
        jupyter_reports = report.jupyter_reports.select_related("upload").all()

        # 🧩 Intentar obtener upload explícito si se pasó como argumento
        upload = None
        if upload_id:
            try:
                upload = DataUpload.objects.get(id=upload_id)
            except DataUpload.DoesNotExist:
                print(f"⚠️ Upload with id={upload_id} not found.")

        total_metrics = 0
        for jupyter_report in jupyter_reports:
            jupyter_upload = jupyter_report.upload

            # 📊 Procesa métricas del HTML (parser ya maneja tablas y KPIs)
            with default_storage.open(jupyter_report.file.name, "r") as f:
                metric_count = process_jupyter_metrics(
                    f, report, jupyter_upload, file_entries=file_entries
                )
                total_metrics += metric_count
                print(
                    f"✅ {metric_count} metrics parsed from HTML: {jupyter_report.file.name}"
                )

        print(f"✅ Metrics processing complete for report {report_id}")
        return f"Processed {total_metrics} HTML metrics."

    except Exception as e:
        print(f"❌ Error in process_metrics_task for report {report_id}: {str(e)}")
        return None


@shared_task
def notify_team_new_report_requested(
    report_id, user_email, dataset_name, organization_name
):
    subject = f"📝 New Report Requested by {user_email}"
    recipient = settings.ADMIN_USER_EMAIL
    sender = settings.DEFAULT_FROM_EMAIL

    if not recipient:
        return

    context = {
        "report_id": report_id,
        "user_email": user_email,
        "dataset_name": dataset_name,
        "organization_name": organization_name,
    }

    html_message = render_to_string(
        "dashboard/analytics/emails/notify_team_new_report_requested.html", context
    )

    send_mail(subject, "", sender, [recipient], html_message=html_message)


@shared_task
def process_dynamic_dashboard_task(report_id, upload_id=None, stored_path=None):
    try:
        report = Report.objects.select_related("dataset").get(id=report_id)
        upload = DataUpload.objects.get(id=upload_id) if upload_id else None

        if not stored_path:
            raise ValueError("stored_path is required to locate the dashboard CSV.")

        with default_storage.open(stored_path, "rb") as file:
            df = pd.read_csv(file)

        if df.empty:
            raise ValueError("Uploaded CSV is empty.")

        config = generate_dashboard_config(df)
        validate_dashboard_config(config)

        # 🗂 Guardar archivo CSV como parte del Metric
        file_name = os.path.basename(stored_path)
        temp_path = f"metrics_temp/{uuid.uuid4().hex}_{file_name}"

        with default_storage.open(stored_path, "rb") as f:
            saved_path = default_storage.save(temp_path, f)

        # 🧩 Crear Metric
        metric = Metric.objects.create(
            report=report,
            source_upload=upload,
            type="dynamic_csv_dashboard",
            name="Dynamic Dashboard",
            file=saved_path,
            is_preview=True,
        )

        # Asociar config al Metric
        DynamicDashboardConfig.objects.create(
            metric=metric,
            config=config,
        )

        # Marcar como procesado
        report.processed = True
        report.save(update_fields=["processed"])

        print(f"✅ Dashboard config and metric created for report {report.id}")
        return f"Dashboard processed successfully for report {report.id}"

    except Exception as e:
        print(f"❌ Error in process_dynamic_dashboard_task: {str(e)}")
        return None
