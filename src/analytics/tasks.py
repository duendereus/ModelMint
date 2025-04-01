from celery import shared_task
from accounts.models import User, Organization
from .models import DataUpload
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


@shared_task
def test_task():
    return "Celery is working!"

@shared_task(bind=True)
def finalize_large_upload(self, title, job_instructions, file_key, user_id, org_id):
    try:
        user = User.objects.get(id=user_id)
        organization = Organization.objects.get(id=org_id)

        DataUpload.objects.create(
            title=title,
            job_instructions=job_instructions,
            uploaded_by=user,
            organization=organization,
            file=file_key,
            status="uploaded"
        )

        logger.info(f"✅ [CELERY] File {file_key} registered in DataUpload by task")

    except Exception as e:
        logger.exception(f"❌ [CELERY] Error in finalize_large_upload: {e}")