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

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def finalize_large_upload(self, upload_id):
    try:
        upload = DataUpload.objects.get(id=upload_id)
        temp_file_path = upload.file

        logger.info(f"🚀 Starting upload to S3: {temp_file_path}")

        # Slugify organization name (you could also precompute and store slug in model if preferred)
        org_slug = upload.organization.name.lower().replace(" ", "_")

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )

        s3_key = f"uploads/{org_slug}/data/{uuid.uuid4()}_{os.path.basename(temp_file_path)}"
        logger.info(f"🗝️ Target S3 key: {s3_key}")

        presigned = s3_client.generate_presigned_post(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=s3_key,
            Fields={},
            Conditions=[
                ["starts-with", "$key", f"uploads/{org_slug}/data/"],
                ["content-length-range", 0, settings.MAX_UPLOAD_SIZE_BYTES],
            ],
            ExpiresIn=3600
        )
        logger.info("✅ Presigned POST generated")

        with default_storage.open(temp_file_path, "rb") as f:
            multipart = MultipartEncoder(
                fields={**presigned['fields'], "file": (os.path.basename(temp_file_path), f)}
            )
            res = requests.post(
                presigned["url"],
                data=multipart,
                headers={"Content-Type": multipart.content_type},
                timeout=600
            )

        if res.status_code == 204:
            upload.status = "uploaded"
            upload.file = s3_key
            logger.info(f"✅ File uploaded to S3: {s3_key}")
        else:
            upload.status = "failed"
            logger.error(f"🔥 Upload failed → {res.status_code} — {res.text}")

        upload.save()

    except Exception as e:
        logger.exception(f"❌ finalize_large_upload failed (ID {upload_id})")
        DataUpload.objects.filter(id=upload_id).update(status="failed")
        raise self.retry(exc=e)

    finally:
        # Ensure cleanup runs no matter what
        if default_storage.exists(temp_file_path):
            default_storage.delete(temp_file_path)
            logger.info("🧹 Temporary file deleted")