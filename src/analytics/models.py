from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils.timezone import now
from .utils.utils import (
    upload_to_metric,
    validate_jupyter_extension,
    upload_to_jupyter_report,
)
from accounts.models import Organization, OrganizationMembership
import boto3
from django_ckeditor_5.fields import CKEditor5Field

User = get_user_model()


class DataSet(models.Model):
    """
    A logical group of related data uploads (versioned dataset uploads).
    """

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="datasets"
    )
    name = models.CharField(
        max_length=255, help_text="Name of the dataset (e.g. 'Monthly Sales')"
    )
    description = models.TextField(
        blank=True, help_text="Optional description of the dataset"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_datasets"
    )
    processed = models.BooleanField(default=False)  # ✅ NEW
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("organization", "name")
        ordering = ["organization", "name"]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class DataUpload(models.Model):
    """
    Model to handle file uploads for customer data processing.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("uploading", "Uploading"),
        ("uploaded", "Uploaded"),
        ("failed", "Failed"),
    ]
    OPERATION_CHOICES = [
        ("create", "Create New Dataset"),
        ("append", "Append to Existing"),
        ("replace", "Replace Dataset"),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="data_uploads"
    )
    uploaded_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="uploads"
    )
    title = models.CharField(max_length=255)
    file = models.CharField(max_length=1024, blank=True, null=True)
    drive_link = models.URLField(blank=True, null=True)

    dataset = models.ForeignKey(
        DataSet, on_delete=models.CASCADE, related_name="uploads", null=True, blank=True
    )
    operation = models.CharField(
        max_length=10, choices=OPERATION_CHOICES, default="create"
    )
    version = models.PositiveIntegerField(default=1)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    removed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "organization", "dataset", "-version"]

    def __str__(self):
        return f"{self.title} - {self.organization.name} - v{self.version}"

    def get_presigned_url(self, expires_in=3600):
        """Generate a pre-signed URL for private file access (valid for 1 hour)."""
        if not self.file:
            return None

        if not settings.USE_S3:
            return f"{settings.MEDIA_URL}{self.file}"

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )

        try:
            return s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": self.file},
                ExpiresIn=expires_in,
            )
        except Exception:
            return None

    def clean(self):
        if not self.organization_id:
            raise ValidationError("Organization must be set before validation.")

        if not self.uploaded_by:
            raise ValidationError("uploaded_by must be set before saving.")

        if (
            self.uploaded_by != self.organization.owner
            and not OrganizationMembership.objects.filter(
                user=self.uploaded_by, organization=self.organization
            ).exists()
        ):
            raise ValidationError(
                "Only the organization owner or members can upload data."
            )

        # ✅ Nueva cláusula: requiere al menos file o drive_link
        if not self.file and not self.drive_link:
            raise ValidationError("You must provide either a file or a drive link.")

    def save(self, *args, **kwargs):
        self.clean()

        # Auto-increment version if part of dataset
        if self.dataset and not self.pk:
            last_upload = (
                DataUpload.objects.filter(dataset=self.dataset)
                .order_by("-version")
                .first()
            )
            self.version = (last_upload.version + 1) if last_upload else 1

        if not self.title:
            dataset_part = self.dataset.name if self.dataset else "upload"
            date_part = (
                self.created_at.strftime("%Y-%m-%d")
                if self.created_at
                else now().strftime("%Y-%m-%d")
            )
            version_part = f"v{self.version}"
            self.title = f"{dataset_part}_{date_part}_{version_part}".lower().replace(
                " ", "_"
            )

        super().save(*args, **kwargs)


class Report(models.Model):
    dataset = models.ForeignKey(
        DataSet, on_delete=models.CASCADE, related_name="reports"
    )
    title = models.CharField(max_length=255)
    description = CKEditor5Field(config_name="default")
    upload = models.ForeignKey(
        DataUpload,
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name="reports",
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.dataset.name})"


class Metric(models.Model):
    METRIC_TYPES = [
        ("table", "Table"),
        ("plot", "Plot"),
        ("single_value", "Single Value"),
        ("text", "Text"),
    ]

    report = models.ForeignKey(
        Report, on_delete=models.CASCADE, related_name="metrics", null=True, blank=True
    )
    source_upload = models.ForeignKey(
        "analytics.DataUpload",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_metrics",
        help_text="Original DataUpload used to generate this metric.",
    )

    type = models.CharField(max_length=20, choices=METRIC_TYPES)
    name = models.CharField(max_length=255, help_text="Name of the metric")
    file = models.FileField(
        upload_to=upload_to_metric, blank=True, null=True, max_length=512
    )
    value = CKEditor5Field(blank=True, null=True)
    position = models.PositiveIntegerField(default=0)
    is_preview = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("report", "position")
        ordering = ["report__dataset__organization", "report__dataset", "-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_type_display()}) - {self.report.title}"

    def save(self, *args, **kwargs):
        if (
            self.position is None
            or Metric.objects.filter(report=self.report, position=self.position)
            .exclude(id=self.id)
            .exists()
        ):
            max_position = (
                Metric.objects.filter(report=self.report).aggregate(
                    models.Max("position")
                )["position__max"]
                or 0
            )
            self.position = max_position + 1

        super().save(*args, **kwargs)

    def get_presigned_url(self, expires_in=3600):
        if not self.file:
            return None

        if not settings.USE_S3:
            return f"{settings.MEDIA_URL}{self.file}"

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )

        try:
            return s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": self.file.name,
                },
                ExpiresIn=expires_in,
            )
        except Exception:
            return None


class TableMetric(models.Model):
    """
    Stores table data for a metric.
    Instead of storing a CSV file, we store the processed table in JSON format.
    """

    metric = models.OneToOneField(
        Metric, on_delete=models.CASCADE, related_name="table_data"
    )
    columns = models.JSONField(help_text="Column names of the table")
    data = models.JSONField(help_text="Row data stored as JSON")  # Stores table rows

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Table Data for {self.metric.name}"


class JupyterReport(models.Model):
    report = models.ForeignKey(
        "Report",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="jupyter_reports",
    )
    upload = models.ForeignKey(
        "DataUpload", on_delete=models.CASCADE, null=True, blank=True
    )
    file = models.FileField(
        upload_to=upload_to_jupyter_report,
        validators=[validate_jupyter_extension],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"JupyterReport for {self.report} (v{self.upload.version if self.upload else 'N/A'})"
