from celery import shared_task
from .models import DataUpload
from django.contrib.auth import get_user_model
import logging
import requests

logger = logging.getLogger(__name__)

User = get_user_model()


@shared_task
def test_task():
    return "Celery is working!"


@shared_task
def upload_to_s3_via_presigned_url(data_upload_id, file_content, presigned_url):
    try:
        upload = DataUpload.objects.get(id=data_upload_id)
        upload.status = "uploading"
        upload.save()

        response = requests.put(
            presigned_url,
            data=file_content,
            headers={"Content-Type": "application/octet-stream"}
        )

        if response.status_code == 200:
            upload.status = "uploaded"
        else:
            upload.status = "failed"
            upload.processing_notes = f"S3 responded with status {response.status_code}"
        upload.save()

    except DataUpload.DoesNotExist:
        logger.error(f"Upload ID {data_upload_id} not found")
    except Exception as e:
        try:
            upload.status = "failed"
            upload.processing_notes = f"Error during upload: {str(e)}"
            upload.save()
        except:
            logger.error(f"Unhandled exception while updating DataUpload {data_upload_id}: {str(e)}")
