from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from accounts.models import Organization
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
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="lab_notebooks/")
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
