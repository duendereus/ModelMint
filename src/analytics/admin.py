from django.contrib import admin
from .models import DataSet, DataUpload, Metric, TableMetric, JupyterReport
from django.utils.html import format_html
from django.contrib import messages


@admin.register(DataSet)
class DataSetAdmin(admin.ModelAdmin):
    """
    Admin configuration for versioned dataset groups.
    """

    list_display = ("name", "organization", "created_by", "processed", "created_at")
    search_fields = ("name", "organization__name", "created_by__email")
    list_filter = ("processed", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ["organization", "created_by"]


@admin.register(DataUpload)
class DataUploadAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "organization",
        "uploaded_by",
        "dataset",
        "operation",
        "version",
        "created_at",
        "used_for_processing",
        "status",
    )
    list_filter = (
        "used_for_processing",
        "created_at",
        "status",
        "operation",
        "dataset",
    )
    search_fields = (
        "title",
        "dataset__name",
        "organization__name",
        "uploaded_by__email",
    )

    readonly_fields = ("version", "created_at", "updated_at")

    fieldsets = (
        (
            "Upload Info",
            {
                "fields": (
                    "title",
                    "organization",
                    "uploaded_by",
                    "dataset",
                    "operation",
                    "file",
                    "drive_link",
                    "job_instructions",
                )
            },
        ),
        (
            "Processing Status",
            {"fields": ("used_for_processing", "processing_notes")},
        ),
        ("Upload Status", {"fields": ("status",)}),
        (
            "Version & Timestamps",
            {"fields": ()},
        ),
    )

    def has_change_permission(self, request, obj=None):
        if obj and obj.used_for_processing:
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
        "dataset",
        # "source_upload",
        "type",
        "position",
        "created_at",
        "is_preview",
        # "preview_data",
    )
    list_filter = ("type", "dataset__organization", "is_preview")
    search_fields = ("name", "dataset__name", "dataset__organization__name")
    ordering = ["dataset__organization", "dataset", "-created_at"]
    list_editable = ("position",)
    readonly_fields = ("created_at", "updated_at")

    inlines = [TableMetricInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("dataset", "dataset__organization", "source_upload")
        )

    def preview_data(self, obj):
        if obj.type == "table" and hasattr(obj, "table_data") and obj.table_data.data:
            return format_html(
                "<pre style='max-width:400px; max-height:100px; overflow:auto; white-space:pre-wrap;'>{}</pre>",
                str(obj.table_data.data[:3]),
            )
        return "-"

    preview_data.short_description = "Table Preview"

    def save_model(self, request, obj, form, change):
        obj.save()
        if hasattr(obj, "_warning_message"):
            self.message_user(request, obj._warning_message, level=messages.WARNING)


@admin.register(JupyterReport)
class JupyterReportAdmin(admin.ModelAdmin):
    list_display = ("dataset", "upload", "uploaded_at", "file_link")
    list_filter = ("uploaded_at", "dataset__organization")
    search_fields = ("dataset__name", "upload__title", "dataset__organization__name")
    readonly_fields = ("uploaded_at", "file_link")
    autocomplete_fields = ["dataset", "upload"]

    def file_link(self, obj):
        if obj.file:
            return format_html(
                "<a href='{}' target='_blank'>📄 View Report</a>", obj.file.url
            )
        return "No file"

    file_link.short_description = "Notebook File"
