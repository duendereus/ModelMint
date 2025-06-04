from celery import shared_task
from analytics.models import DataUpload, Metric
from analytics.utils.process_jupyter_metrics import process_jupyter_metrics
from analytics.utils.jupyter_parser import clean_metric_name
from django.core.files.storage import default_storage
import os


@shared_task
def test_task():
    return "Celery is working!"


@shared_task
def process_metrics_task(upload_id, report_path, file_entries):
    """
    Procesa métricas del HTML + archivos complementarios.
    `file_entries`: lista de diccionarios con:
        - stored_path: ubicación del archivo guardado en storage (S3 o local)
        - original_name: nombre original del archivo (para usar como nombre de métrica)
    """
    try:
        upload = DataUpload.objects.select_related("dataset").get(id=upload_id)
        dataset = upload.dataset

        with default_storage.open(report_path, "r") as f:
            metric_count = process_jupyter_metrics(f, dataset, upload)
        print(f"✅ {metric_count} metrics parsed from HTML for upload {upload_id}")

        VALID_TABLE_EXTENSIONS = {".csv", ".xls", ".xlsx"}
        for entry in file_entries:
            stored_path = entry["stored_path"]
            original_name = entry["original_name"]
            ext = os.path.splitext(original_name)[1].lower()

            if ext not in VALID_TABLE_EXTENSIONS:
                print(f"⚠️ Skipped unsupported file: {original_name}")
                continue

            with default_storage.open(stored_path, "rb") as file:
                Metric.objects.create(
                    dataset=dataset,
                    source_upload=upload,
                    type="table",
                    name=clean_metric_name(original_name),
                    file=file,
                )

        print(f"✅ Complementary files processed for upload {upload_id}")
        return f"Processed {metric_count} HTML metrics and {len(file_entries)} files."

    except Exception as e:
        print(f"❌ Error in process_metrics_task for upload {upload_id}: {str(e)}")
        return None
