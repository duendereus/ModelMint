from celery import shared_task
from django.core.files.storage import default_storage
from labs.models import LabNotebook, NotebookVersion
from labs.utils.process_lab_notebook_metrics import process_lab_metrics


@shared_task
def process_lab_notebook_task(notebook_id, version_obj_id, file_entries=None):
    try:
        notebook = LabNotebook.objects.get(id=notebook_id)
        version_obj = NotebookVersion.objects.get(id=version_obj_id)

        html_path = version_obj.html_file.name
        with default_storage.open(html_path, "rb") as f:
            metric_count = process_lab_metrics(
                f, notebook, version_obj=version_obj, file_entries=file_entries or []
            )

        print(
            f"✅ {metric_count} total metrics stored for {notebook.title} (v{version_obj.version})"
        )
        return f"Processed v{version_obj.version} for LabNotebook {notebook_id}"

    except Exception as e:
        print(f"❌ Error processing LabNotebook {notebook_id}: {str(e)}")
        return f"❌ Error: {str(e)}"
