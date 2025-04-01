from celery import shared_task
from .models import DataUpload
from django.contrib.auth import get_user_model
import logging
from requests_toolbelt.multipart.encoder import MultipartEncoder
import requests
import boto3
from django.core.files.storage import default_storage
from django.conf import settings
import os
import uuid

logger = logging.getLogger(__name__)

User = get_user_model()


@shared_task
def test_task():
    return "Celery is working!"

@shared_task
def finalize_large_upload(upload_id):
    try:
        upload = DataUpload.objects.get(id=upload_id)
        temp_file_path = upload.file

        logger.info(f"🚀 Uploading temp file to S3: {temp_file_path}")

        with default_storage.open(temp_file_path, "rb") as f:
            file_content = f.read()

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )

        s3_key = f"uploads/{upload.organization.slug}/data/{uuid.uuid4()}_{os.path.basename(temp_file_path)}"

        presigned = s3_client.generate_presigned_post(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=s3_key,
            Fields={},
            Conditions=[
                ["starts-with", "$key", f"uploads/{upload.organization.slug}/data/"],
                ["content-length-range", 0, settings.MAX_UPLOAD_SIZE_BYTES],
            ],
            ExpiresIn=3600
        )

        multipart = MultipartEncoder(fields={**presigned['fields'], "file": (os.path.basename(temp_file_path), file_content)})
        res = requests.post(presigned["url"], data=multipart, headers={"Content-Type": multipart.content_type})

        if res.status_code == 204:
            upload.status = "uploaded"
            upload.file = s3_key
            logger.info("✅ S3 upload completed")
        else:
            upload.status = "failed"
            logger.error(f"🔥 S3 upload failed: {res.status_code} - {res.text}")

        upload.save()
        default_storage.delete(temp_file_path)

    except Exception as e:
        logger.exception(f"🔥 Finalize upload failed for ID {upload_id}")
        DataUpload.objects.filter(id=upload_id).update(status="failed")
