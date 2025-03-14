from celery import shared_task
from .models import DataUpload
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


@shared_task
def test_task():
    return "Celery is working!"


@shared_task
def save_uploaded_file(data_upload_id):
    """
    Celery task to handle background file processing after upload.
    """
    try:
        upload = DataUpload.objects.get(id=data_upload_id)

        # ✅ Confirm File Exists
        if not upload.file:
            return f"Error: No file found for upload ID {data_upload_id}."

        # ✅ Log File Path (For Debugging)
        logger.info(f"Processing file: {upload.file.url}")

        # ✅ OPTIONAL: If you need to process the file later
        # with upload.file.open() as f:
        #     file_content = f.read()
        #     process_file_data(file_content)

        return f"File '{upload.file.name}' processed successfully."

    except DataUpload.DoesNotExist:
        return f"Error: DataUpload with ID {data_upload_id} not found."
    except Exception as e:
        return f"Error processing upload: {str(e)}"
