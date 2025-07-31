from celery import shared_task
from django.core.files.storage import default_storage
from django.core.files.base import File
from labs.models import LabNotebook, NotebookVersion, NotebookMetric
from labs.utils.process_lab_notebook_metrics import process_lab_metrics
from analytics.utils.jupyter_parser import clean_metric_name
import os


@shared_task
def process_lab_notebook_task(notebook_id, version_obj_id, file_entries=None):
    try:
        notebook = LabNotebook.objects.get(id=notebook_id)
        version_obj = NotebookVersion.objects.get(id=version_obj_id)

        html_path = version_obj.html_file.name
        total_metrics = 0

        with default_storage.open(html_path, "rb") as f:
            metric_count = process_lab_metrics(f, notebook, version_obj=version_obj)
            total_metrics += metric_count
            print(
                f"✅ {metric_count} HTML metrics parsed for {notebook.title} (v{version_obj.version})"
            )

        VALID_TABLE_EXTENSIONS = {".csv", ".xls", ".xlsx"}

        for entry in file_entries or []:
            stored_path = entry["stored_path"]
            original_name = entry["original_name"]
            ext = os.path.splitext(original_name)[1].lower()

            if ext not in VALID_TABLE_EXTENSIONS:
                print(f"⚠️ Skipped unsupported file: {original_name}")
                continue

            with default_storage.open(stored_path, "rb") as file:
                NotebookMetric.objects.create(
                    notebook=notebook,
                    version_obj=version_obj,
                    type="table",
                    name=clean_metric_name(original_name),
                    file=File(file, name=os.path.basename(stored_path)),
                    position=NotebookMetric.objects.filter(
                        version_obj=version_obj
                    ).count(),
                )
                total_metrics += 1

        print(
            f"✅ {total_metrics} total metrics stored for {notebook.title} (v{version_obj.version})"
        )
        return f"Processed v{version_obj.version} for LabNotebook {notebook_id}"

    except Exception as e:
        print(f"❌ Error processing LabNotebook {notebook_id}: {str(e)}")
        return f"❌ Error: {str(e)}"
