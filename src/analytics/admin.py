from django.contrib import admin
from .models import (
    DataSet,
    DataUpload,
    Metric,
    TableMetric,
    JupyterReport,
    Report,
    DynamicDashboardConfig,
)
from django.utils.html import format_html


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
        "status",
    )
    list_filter = (
        "created_at",
        "status",
        "operation",
        "dataset",
        "organization",
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
                )
            },
        ),
        ("Upload Status", {"fields": ("status",)}),
        (
            "Version & Timestamps",
            {"fields": ("version", "created_at", "updated_at")},
        ),
    )


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "type",
        "dataset",
        "upload",
        "created_by",
        "processed",
        "created_at",
    )
    list_filter = (
        "processed",
        "type",
        "dataset__organization",
    )
    search_fields = (
        "title",
        "dataset__name",
        "dataset__organization__name",
    )
    readonly_fields = ("created_at",)
    autocomplete_fields = ["dataset", "upload", "created_by"]
    ordering = ["-created_at"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "description",
                    "type",
                    "example_file",
                    "dataset",
                    "upload",
                    "created_by",
                    "processed",
                    "created_at",
                )
            },
        ),
    )


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
        "get_dataset",
        "type",
        "position",
        "created_at",
        "is_preview",
    )
    list_filter = ("type", "report__dataset__organization", "is_preview")
    search_fields = (
        "name",
        "report__dataset__name",
        "report__dataset__organization__name",
    )
    ordering = ["report__dataset__organization", "report__dataset", "-created_at"]
    list_editable = ("position",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [TableMetricInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "report__dataset", "report__dataset__organization", "source_upload"
            )
        )

    def get_dataset(self, obj):
        return obj.report.dataset.name

    get_dataset.short_description = "Dataset"


@admin.register(JupyterReport)
class JupyterReportAdmin(admin.ModelAdmin):
    list_display = ("id", "get_dataset", "upload", "uploaded_at", "file_link")
    list_filter = ("uploaded_at", "report__dataset__organization")
    search_fields = (
        "report__dataset__name",
        "upload__title",
        "report__dataset__organization__name",
    )
    readonly_fields = ("uploaded_at", "file_link")
    autocomplete_fields = ["report", "upload"]

    def get_dataset(self, obj):
        if obj.report and obj.report.dataset:
            return obj.report.dataset.name
        return "(No report)"

    get_dataset.short_description = "Dataset"

    def file_link(self, obj):
        if obj.file:
            return format_html(
                "<a href='{}' target='_blank'>📄 View Report</a>", obj.file.url
            )
        return "No file"

    file_link.short_description = "Notebook File"


@admin.register(DynamicDashboardConfig)
class DynamicDashboardConfigAdmin(admin.ModelAdmin):
    list_display = (
        "metric",
        "created_at",
    )
    readonly_fields = ("created_at",)
    search_fields = ("metric__name", "metric__report__title")
    list_select_related = ("metric",)
