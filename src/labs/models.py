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
import uuid


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


class NotebookMetric(models.Model):
    notebook = models.ForeignKey(
        LabNotebook, on_delete=models.CASCADE, related_name="metrics"
    )
    version = models.PositiveIntegerField()
    type = models.CharField(max_length=20, choices=Metric.METRIC_TYPES)
    name = models.CharField(max_length=255)
    value = CKEditor5Field(blank=True, null=True)
    file = models.FileField(upload_to=upload_to_metric_labs, blank=True, null=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.notebook} - {self.name}"

    class Meta:
        unique_together = ("notebook", "version", "position")
        ordering = ["notebook", "-version", "position"]


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
