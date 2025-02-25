from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from accounts.models import User, Organization


# Register your models here.
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin interface for the User model.
    Extends the default UserAdmin class to include custom fields and functionality.
    """

    list_display = ("email", "username", "phone_number", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active", "groups")
    search_fields = ("email", "username", "phone_number")
    ordering = ("-created",)
    readonly_fields = ("created", "updated")

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Personal Info", {"fields": ("phone_number",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Groups and Permissions", {"fields": ("groups", "user_permissions")}),
        ("Important Dates", {"fields": ("created", "updated")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "username",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """
    Admin class for managing organizations in the Django admin panel.
    """

    list_display = ("name", "owner", "created_at")
    search_fields = (
        "name",
        "owner__email",
        "owner__username",
    )
    list_filter = ("created_at",)
    ordering = ("-created_at",)
    raw_id_fields = ("owner", "users")
    filter_horizontal = ("users",)

    fieldsets = (
        (None, {"fields": ("name", "owner")}),
        ("Users", {"fields": ("users",)}),
        ("Metadata", {"fields": ("created_at",)}),
    )

    readonly_fields = ("created_at",)
