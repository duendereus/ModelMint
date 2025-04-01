from celery import shared_task
from .models import DataUpload
from django.contrib.auth import get_user_model
import logging
from requests_toolbelt.multipart.encoder import MultipartEncoder


logger = logging.getLogger(__name__)

User = get_user_model()


@shared_task
def test_task():
    return "Celery is working!"

@shared_task
def finalize_large_upload(upload_id, presigned_url, presigned_fields, file_content):
    import requests
    import json

    logger.info(f"🚀 Starting S3 upload for DataUpload ID: {upload_id}")
    try:
        s3_form = json.loads(presigned_fields)
        files = { "file": file_content }
        multipart_data = s3_form.copy()
        multipart_data.update(files)

        # Convert fields to multipart form data
        form = MultipartEncoder(fields={**s3_form, "file": ("upload.csv", file_content)})

        res = requests.post(presigned_url, data=form, headers={"Content-Type": form.content_type})
        logger.info(f"🧾 S3 response: {res.status_code}, {res.text}")

        # Update upload status
        DataUpload.objects.filter(id=upload_id).update(status="uploaded")

    except Exception as e:
        logger.exception(f"🔥 Error during background upload for ID: {upload_id}")
        DataUpload.objects.filter(id=upload_id).update(status="failed")
