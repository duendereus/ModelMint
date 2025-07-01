from django.contrib import admin
from django.utils.html import format_html
from .models import (
    LabNotebook,
    NotebookVersion,
    NotebookAccessRequest,
    NotebookMetric,
    NotebookTableMetric,
)
from .forms import LabNotebookAdminForm


@admin.register(LabNotebook)
class LabNotebookAdmin(admin.ModelAdmin):
    form = LabNotebookAdminForm

    list_display = (
        "title",
        "organization",
        "created_by",
        "is_public",
        "active",
        "created_at",
        "notebook_file_link",
    )
    list_filter = ("organization", "is_public", "active")
    search_fields = ("title", "slug", "created_by__email")

    def notebook_file_link(self, obj):
        if obj.file:
            return format_html(
                '<a href="{}" target="_blank">📄 Ver archivo</a>',
                obj.file.url,
            )
        return "—"

    notebook_file_link.short_description = "Archivo"


@admin.register(NotebookVersion)
class NotebookVersionAdmin(admin.ModelAdmin):
    list_display = (
        "notebook",
        "version",
        "uploaded_by",
        "created_at",
        "html_file_link",
    )
    list_filter = ("notebook__organization",)
    search_fields = ("notebook__title", "uploaded_by__email")

    def html_file_link(self, obj):
        if obj.html_file:
            return format_html(
                '<a href="{}" target="_blank">📄 Ver archivo</a>', obj.html_file.url
            )
        return "—"

    html_file_link.short_description = "Archivo HTML"


@admin.register(NotebookMetric)
class NotebookMetricAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "notebook",
        "get_version",
        "type",
        "position",
        "created_at",
        "file_link",
    )
    list_filter = ("type", "notebook__organization")
    search_fields = ("name", "notebook__title")

    def get_version(self, obj):
        return obj.version_obj.version

    get_version.short_description = "Versión"

    def file_link(self, obj):
        if obj.file:
            return format_html(
                '<a href="{}" target="_blank">📎 Descargar</a>', obj.file.url
            )
        return "—"

    file_link.short_description = "Archivo"


@admin.register(NotebookTableMetric)
class NotebookTableMetricAdmin(admin.ModelAdmin):
    list_display = (
        "metric",
        "num_columns",
        "num_rows",
        "created_at",
    )

    def num_columns(self, obj):
        return len(obj.columns)

    def num_rows(self, obj):
        return len(obj.data)


@admin.register(NotebookAccessRequest)
class NotebookAccessRequestAdmin(admin.ModelAdmin):
    list_display = (
        "notebook",
        "email",
        "is_verified",
        "requested_at",
        "expires_at",
        "session_token",
    )
    list_filter = ("is_verified", "notebook__organization")
    search_fields = ("email", "notebook__title")
