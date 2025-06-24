from django.contrib import admin
from dashboard.models import DashboardSelection, DashboardMetricOrder


class DashboardMetricOrderInline(admin.TabularInline):
    model = DashboardMetricOrder
    extra = 0
    ordering = ["position"]
    autocomplete_fields = ["metric"]


class DashboardSelectionAdmin(admin.ModelAdmin):
    """
    Admin interface for managing Dashboard Selections.
    """

    list_display = ("organization", "updated_at")
    search_fields = ("organization__name",)
    inlines = [DashboardMetricOrderInline]
    autocomplete_fields = ["metrics"]
    filter_horizontal = ("metrics",)

    def get_queryset(self, request):
        """
        Filters queryset to show only organizations the user has access to (if needed).
        """
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(organization__owner=request.user)


admin.site.register(DashboardSelection, DashboardSelectionAdmin)
