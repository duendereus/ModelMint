from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .utils import validate_file_extension, upload_to_data_file, upload_to_metric
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
    file = models.FileField(
        upload_to=upload_to_data_file, validators=[validate_file_extension]
    )
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


class Metric(models.Model):
    """
    Stores metrics, tables, plots, and other analytical
    results generated from DataUpload processing.
    """

    METRIC_TYPES = [
        ("table", "Table"),
        ("plot", "Plot"),
        ("single_value", "Single Value"),
        ("text", "Text"),
    ]

    datasource = models.ForeignKey(
        DataUpload, on_delete=models.CASCADE, related_name="metrics"
    )
    type = models.CharField(max_length=20, choices=METRIC_TYPES)
    name = models.CharField(max_length=255, help_text="Name of the metric")
    file = models.FileField(
        upload_to=upload_to_metric, blank=True, null=True
    )  # For plot or file metrics
    value = models.TextField(blank=True, null=True)  # For single_value or text
    position = models.PositiveIntegerField(
        default=0, help_text="Display order of metric"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("datasource", "position")
        ordering = ["datasource__organization", "datasource", "-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_type_display()}) - {self.datasource.title}"

    def save(self, *args, **kwargs):
        """
        Ensures the metric position is unique within a datasource.
        If the position is taken, it does NOT auto-increment but instead adds a warning.
        """
        if self.position is None:
            self.position = 0

        # Check for conflicting positions
        conflicting_metric = (
            Metric.objects.filter(datasource=self.datasource, position=self.position)
            .exclude(id=self.id)
            .first()
        )

        if conflicting_metric:
            # Store the error in a non-blocking way
            self._warning_message = f"⚠️ Metric position {self.position} is already taken within this datasource. Please select a different position."
            return  # Stop save execution but do not raise an error

        super().save(*args, **kwargs)


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
