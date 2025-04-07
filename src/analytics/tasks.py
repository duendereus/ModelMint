from celery import shared_task
from .models import DataUpload
import logging
import boto3
from django.conf import settings
import time

logger = logging.getLogger(__name__)


@shared_task
def test_task():
    return "Celery is working!"

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def finalize_large_upload(self, upload_id):
    try:
        upload = DataUpload.objects.get(id=upload_id)
        s3_key = upload.file

        logger.info(f"🚀 Finalizing upload: checking S3 for key {s3_key}")

        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )

        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"🔎 Attempt {attempt}: Checking if file exists in S3...")
                s3.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=s3_key)
                upload.status = "uploaded"
                upload.save()
                logger.info(f"✅ File found in S3 and marked as uploaded: {s3_key}")
                return  # 🎉 Exit if successful
            except s3.exceptions.ClientError as e:
                error_code = e.response.get("Error", {}).get("Code")
                if error_code == "404":
                    logger.warning(f"⚠️ Attempt {attempt}: File not yet available in S3 ({s3_key})")
                    time.sleep(10)  # ⏳ Wait before trying again
                else:
                    logger.error(f"🔥 S3 error: {e}")
                    raise e  # Raise for retry
        # Si después de todos los intentos no se encuentra:
        logger.error(f"❌ File still not found in S3 after {max_attempts} attempts")
        upload.status = "failed"
        upload.save()
        raise Exception("File not found in S3 after multiple attempts")

    except Exception as e:
        logger.exception(f"❌ finalize_large_upload failed (ID {upload_id})")
        DataUpload.objects.filter(id=upload_id).update(status="failed")
        raise self.retry(exc=e)