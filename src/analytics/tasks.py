from celery import shared_task
from .models import DataUpload
from django.contrib.auth import get_user_model
import logging
from django.conf import settings
import boto3

logger = logging.getLogger(__name__)

User = get_user_model()


@shared_task
def test_task():
    return "Celery is working!"


@shared_task
def upload_from_tmp_to_s3(upload_id, file_name):
    try:
        upload = DataUpload.objects.get(id=upload_id)
        upload.status = "uploading"
        upload.save()

        local_path = f"/tmp/uploads/{file_name}"  # This path must exist with file already in it

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )

        with open(local_path, "rb") as f:
            s3_client.upload_fileobj(f, settings.AWS_STORAGE_BUCKET_NAME, upload.file)

        upload.status = "uploaded"
        upload.save()

    except Exception as e:
        if upload_id:
            try:
                upload.status = "failed"
                upload.processing_notes = str(e)
                upload.save()
            except:
                pass

