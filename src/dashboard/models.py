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

    def get_ordered_metrics(self):
        return (
            Metric.objects.filter(dashboardmetricorder__dashboard=self)
            .annotate(order_position=models.F("dashboardmetricorder__position"))
            .order_by("order_position")
        )

    def __str__(self):
        return f"Dashboard Selection for {self.organization.name}"


class DashboardMetricOrder(models.Model):
    """
    Intermediate model to define the order of metrics in DashboardSelection.
    """

    dashboard = models.ForeignKey(DashboardSelection, on_delete=models.CASCADE)
    metric = models.ForeignKey("analytics.Metric", on_delete=models.CASCADE)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position"]
        unique_together = ("dashboard", "metric")

    def __str__(self):
        return f"{self.metric.name} in {self.dashboard.organization.name} (pos: {self.position})"
