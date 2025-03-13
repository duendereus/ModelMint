from django.db import models
from accounts.models import Organization
from analytics.models import Metric


# Create your models here.
class DashboardSelection(models.Model):
    """
    Stores selected metrics to be displayed in the main dashboard.
    Only organization owners can modify this.
    """

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="dashboard_selection"
    )
    metrics = models.ManyToManyField(Metric, related_name="selected_for_dashboard")

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dashboard Selection for {self.organization.name}"
