from celery import shared_task
from analytics.models import Metric, Report
from analytics.utils.process_jupyter_metrics import process_jupyter_metrics
from analytics.utils.jupyter_parser import clean_metric_name
from django.core.files.storage import default_storage
import os


@shared_task
def test_task():
    return "Celery is working!"


@shared_task
def process_metrics_task(report_id, file_entries):
    """
    Procesa métricas del HTML + archivos complementarios usando los JupyterReport asociados.
    `file_entries`: lista de diccionarios con:
        - stored_path: ubicación del archivo guardado en storage (S3 o local)
        - original_name: nombre original del archivo (para usar como nombre de métrica)
    """
    try:
        report = Report.objects.get(id=report_id)
        jupyter_reports = report.jupyter_reports.select_related("upload").all()

        total_metrics = 0
        for jupyter_report in jupyter_reports:
            upload = jupyter_report.upload

            # 📊 Procesa métricas del HTML
            with default_storage.open(jupyter_report.file.name, "r") as f:
                metric_count = process_jupyter_metrics(f, report, upload)
                total_metrics += metric_count
                print(
                    f"✅ {metric_count} metrics parsed from HTML: {jupyter_report.file.name}"
                )

        # 📂 Procesa archivos complementarios
        VALID_TABLE_EXTENSIONS = {".csv", ".xls", ".xlsx"}
        for entry in file_entries:
            stored_path = entry["stored_path"]
            original_name = entry["original_name"]
            ext = os.path.splitext(original_name)[1].lower()

            if ext not in VALID_TABLE_EXTENSIONS:
                print(f"⚠️ Skipped unsupported file: {original_name}")
                continue

            # Solo usamos el último upload procesado (puedes ajustar esta lógica si quieres otro comportamiento)
            latest_upload = jupyter_reports.last().upload if jupyter_reports else None

            with default_storage.open(stored_path, "rb") as file:
                Metric.objects.create(
                    report=report,
                    source_upload=latest_upload,
                    type="table",
                    name=clean_metric_name(original_name),
                    file=file,
                )

        print(f"✅ Complementary files processed for report {report_id}")
        return f"Processed {total_metrics} HTML metrics and {len(file_entries)} files."

    except Exception as e:
        print(f"❌ Error in process_metrics_task for report {report_id}: {str(e)}")
        return None
