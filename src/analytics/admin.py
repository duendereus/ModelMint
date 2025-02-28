from django.contrib import admin
from .models import DataUpload


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
