from celery import shared_task
from .models import DataUpload
from django.contrib.auth import get_user_model
import logging
from django.conf import settings
import boto3
import os

logger = logging.getLogger(__name__)

User = get_user_model()


@shared_task
def test_task():
    return "Celery is working!"
