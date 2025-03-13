from django.contrib import admin
from dashboard.models import DashboardSelection


class DashboardSelectionAdmin(admin.ModelAdmin):
    """
    Admin interface for managing Dashboard Selections.
    """

    list_display = ("organization", "updated_at")  # Show organization and last update
    search_fields = ("organization__name",)  # Allow searching by organization name
    filter_horizontal = ("metrics",)  # Provides a better UI for selecting metrics

    def get_queryset(self, request):
        """
        Filters queryset to show only organizations the user has access to (if needed).
        """
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(organization__owner=request.user)


admin.site.register(DashboardSelection, DashboardSelectionAdmin)
