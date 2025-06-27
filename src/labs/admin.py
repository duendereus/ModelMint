from django.contrib import admin
from .models import LabNotebook, NotebookAccessRequest
from .forms import LabNotebookAdminForm


@admin.register(LabNotebook)
class LabNotebookAdmin(admin.ModelAdmin):
    form = LabNotebookAdminForm

    list_display = ("title", "organization", "created_by", "created_at", "is_public")
    list_filter = ("organization", "is_public")
    search_fields = ("title", "slug", "created_by__email")


@admin.register(NotebookAccessRequest)
class NotebookAccessRequestAdmin(admin.ModelAdmin):
    list_display = ("notebook", "email", "is_verified", "requested_at", "expires_at")
    search_fields = ("email",)
    list_filter = ("is_verified", "notebook__organization")
