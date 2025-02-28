from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .utils import validate_file_extension, upload_to
from accounts.models import Organization, OrganizationMembership

User = get_user_model()


class DataUpload(models.Model):
    """
    Model to handle file uploads for customer data processing.
    """

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="data_uploads"
    )
    uploaded_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="uploads"
    )
    title = models.CharField(
        max_length=255, help_text="A short title describing the data upload."
    )
    file = models.FileField(upload_to=upload_to, validators=[validate_file_extension])
    job_instructions = models.TextField(
        blank=False,
        help_text="Detailed instructions on what needs to be done with the data.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed = models.BooleanField(default=False)
    processing_notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.title} - {self.organization.name}"

    def clean(self):
        """
        Ensures that only users from the same organization OR the owner can upload files.
        """
        if not self.organization_id:
            raise ValidationError("Organization must be set before validation.")

        if not self.uploaded_by:
            raise ValidationError("uploaded_by must be set before saving.")

        # Check if the user is the owner or a member of the organization
        if (
            self.uploaded_by != self.organization.owner
            and not OrganizationMembership.objects.filter(
                user=self.uploaded_by, organization=self.organization
            ).exists()
        ):
            raise ValidationError(
                "Only the organization owner or members can upload data."
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
