from django.utils.text import slugify
from django.db import models
from django.conf import settings
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
    slug = models.SlugField(
        unique=True, blank=True
    )  # <-- blank=True para permitir autogeneración
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="lab_notebooks/")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_public = models.BooleanField(default=False)
    allowed_emails = models.JSONField(blank=True, null=True)
    expires_after_hours = models.PositiveIntegerField(default=24)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:50]  # limita tamaño del slug base
            slug = base_slug
            counter = 1
            while LabNotebook.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


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
