from django.contrib import admin
from .models import DataSet, DataUpload, Metric, TableMetric
from django.utils.html import format_html
from django.contrib import messages
from django import forms
from ckeditor.widgets import CKEditorWidget


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


class DataUploadAdminForm(forms.ModelForm):
    class Meta:
        model = DataUpload
        fields = "__all__"
        widgets = {
            "job_instructions": CKEditorWidget(),
            "processing_notes": CKEditorWidget(),
        }


@admin.register(DataUpload)
class DataUploadAdmin(admin.ModelAdmin):
    form = DataUploadAdminForm
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


class MetricAdminForm(forms.ModelForm):
    class Meta:
        model = Metric
        fields = "__all__"
        widgets = {
            "value": CKEditorWidget(attrs={"class": "wide-ckeditor"}),
        }


@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    form = MetricAdminForm
    list_display = (
        "name",
        "dataset",
        "source_upload",
        "type",
        "position",
        "created_at",
        "preview_data",
    )
    list_filter = ("type", "dataset__organization")
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

    class Media:
        css = {"all": ("admin/custom_admin.css",)}
