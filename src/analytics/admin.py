from django.contrib import admin
from .models import DataUpload, Metric, TableMetric
from django.utils.html import format_html
from django.contrib import messages


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
        "status",
    )
    list_filter = ("processed", "created_at", "status")
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
        ("Upload Status", {"fields": ("status",)}),
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
    readonly_fields = ("columns", "short_data")
    can_delete = False

    def short_data(self, obj):
        """
        Returns a truncated version of the JSON data (limited to 100 characters).
        """
        data_str = str(obj.data)  # Convert JSON to string
        return format_html(
            "<pre style='max-width:400px; white-space:pre-wrap;'>{}</pre>",
            data_str[:100] + "..." if len(data_str) > 100 else data_str,
        )

    short_data.short_description = "Data Preview"  # Admin column name


@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "datasource",
        "datasource_organization",
        "type",
        "position",
        "created_at",
        "preview_data",
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
        """Optimize query performance using select_related to fetch related objects in a single query."""
        return (
            super()
            .get_queryset(request)
            .select_related("datasource", "datasource__organization")
        )

    def preview_data(self, obj):
        """Displays a small preview of the table data in the admin list view."""
        if obj.type == "table" and hasattr(obj, "table_data") and obj.table_data.data:
            return format_html(
                "<pre style='max-width:400px; max-height:100px; overflow:auto; white-space:pre-wrap;'>{}</pre>",
                str(obj.table_data.data[:3]),
            )
        return "-"

    preview_data.short_description = "Table Preview"

    def save_model(self, request, obj, form, change):
        """
        Override save_model to show a warning message instead of throwing an error
        """
        obj.save()
        if hasattr(obj, "_warning_message"):
            self.message_user(request, obj._warning_message, level=messages.WARNING)
