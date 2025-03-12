import os
from celery import Celery

# Set the default Django settings module for Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

# Load Celery config from Django settings with a prefix of CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

# Explicitly set broker_connection_retry_on_startup to True
app.conf.broker_connection_retry_on_startup = True

# Auto-discover tasks from installed Django apps
app.autodiscover_tasks()
