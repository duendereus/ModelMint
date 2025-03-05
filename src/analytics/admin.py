from django.contrib import admin
from .models import DataUpload, Metric, TableMetric
from django.utils.html import format_html


@admin.register(DataUpload)
class DataUploadAdmin(admin.ModelAdmin):
    """
    Admin configuration for managing data uploads.
    """

    list_display = (
        "title",
        "organization",
        "uploaded_by",
        "file",
        "created_at",
        "processed",
    )
    list_filter = ("processed", "created_at")
    search_fields = ("title", "organization__name", "uploaded_by__email", "file")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Upload Info",
            {
                "fields": (
                    "title",
                    "organization",
                    "uploaded_by",
                    "file",
                    "job_instructions",
                )
            },
        ),
        ("Processing Status", {"fields": ("processed", "processing_notes")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    # Optimized Selection
    raw_id_fields = ("uploaded_by",)  # More efficient selection for large user bases
    autocomplete_fields = ["organization"]  # Allows searching organizations

    def has_change_permission(self, request, obj=None):
        """Allow changing only if the file is not processed yet."""
        if obj and obj.processed:
            return False
        return super().has_change_permission(request, obj)


class TableMetricInline(admin.TabularInline):
    model = TableMetric
    readonly_fields = ("columns", "data")
    can_delete = False


@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "datasource",
        "datasource_organization",
        "type",
        "position",
        "created_at",
        "preview_data",  # ✅ Now included in list_display
    )
    list_filter = ("type", "datasource__organization")
    search_fields = ("name", "datasource__title", "datasource__organization__name")
    ordering = ["datasource__organization", "datasource", "-created_at"]
    list_editable = ("position",)
    readonly_fields = ("created_at", "updated_at")

    inlines = [TableMetricInline]

    def datasource_organization(self, obj):
        """Returns the organization name related to the metric's datasource."""
        return obj.datasource.organization.name if obj.datasource.organization else ""

    datasource_organization.short_description = "Organization"

    def get_queryset(self, request):
        """
        Optimizes query performance by using select_related to fetch related objects in a single query.
        """
        return (
            super()
            .get_queryset(request)
            .select_related("datasource", "datasource__organization")
        )

    def preview_data(self, obj):
        """
        Displays a small preview of the table data in the admin list view.
        Shows only the first 3 rows to keep the UI clean.
        """
        if obj.type == "table" and hasattr(obj, "table_data") and obj.table_data.data:
            return format_html(
                "<pre style='max-width:400px; max-height:100px; overflow:auto; white-space:pre-wrap;'>{}</pre>",
                str(obj.table_data.data[:3]),  # ✅ Prevents errors if data is empty
            )
        return "-"

    preview_data.short_description = "Table Preview"
