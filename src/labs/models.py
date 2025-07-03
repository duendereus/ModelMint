from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from analytics.models import Metric
from labs.utils.utils import (
    upload_to_metric_labs,
    upload_to_lab_notebook,
    validate_html_file_extension,
)
from django_ckeditor_5.fields import CKEditor5Field
import uuid, boto3


class LabNotebook(models.Model):
    organization = models.ForeignKey(
        "accounts.Organization", on_delete=models.CASCADE, related_name="lab_notebooks"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_lab_notebooks",
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    description = CKEditor5Field(blank=True)
    file = models.FileField(
        upload_to=upload_to_lab_notebook,
        validators=[validate_html_file_extension],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_public = models.BooleanField(default=False)
    allowed_emails = models.JSONField(blank=True, null=True)
    expires_after_hours = models.PositiveIntegerField(default=24)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()

        # 1. Solo se permite organizaciones tipo "lab"
        if self.organization.type != "lab":
            raise ValidationError(
                "Only lab organizations can be assigned to LabNotebooks."
            )

        # 2. Validar que created_by sea owner o miembro de la organización
        is_owner = self.organization.owner == self.created_by
        is_member = self.organization.members.filter(user=self.created_by).exists()

        if not (is_owner or is_member):
            raise ValidationError("User must be owner or member of the organization.")

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:50]
            slug = base_slug
            counter = 1
            while LabNotebook.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        self.full_clean()
        super().save(*args, **kwargs)


class NotebookVersion(models.Model):
    notebook = models.ForeignKey(
        LabNotebook, on_delete=models.CASCADE, related_name="versions"
    )
    version = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    html_file = models.FileField(
        upload_to=upload_to_lab_notebook, validators=[validate_html_file_extension]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("notebook", "version")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notebook.title} (v{self.version})"


class NotebookMetric(models.Model):
    version_obj = models.ForeignKey(
        "NotebookVersion", on_delete=models.CASCADE, related_name="metrics"
    )
    notebook = models.ForeignKey(
        LabNotebook, on_delete=models.CASCADE, related_name="metrics"
    )
    type = models.CharField(max_length=30, choices=Metric.METRIC_TYPES)
    name = models.CharField(max_length=255)
    value = CKEditor5Field(blank=True, null=True)
    file = models.FileField(upload_to=upload_to_metric_labs, blank=True, null=True)
    position = models.PositiveIntegerField(default=0)
    is_preview = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.notebook} - {self.name}"

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

    class Meta:
        unique_together = ("version_obj", "position")
        ordering = ["notebook", "version_obj__version", "position"]


class NotebookTableMetric(models.Model):
    metric = models.OneToOneField(
        NotebookMetric, on_delete=models.CASCADE, related_name="table_data"
    )
    columns = models.JSONField(help_text="Column names of the table")
    data = models.JSONField(help_text="Row data stored as JSON")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Table Data for {self.metric.name}"


class NotebookAccessRequest(models.Model):
    notebook = models.ForeignKey(
        LabNotebook, on_delete=models.CASCADE, related_name="access_requests"
    )
    email = models.EmailField()
    otp_code = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    requested_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    session_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return f"{self.email} → {self.notebook.title}"
