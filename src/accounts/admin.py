from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from accounts.models import User, Organization, OrganizationMembership
from django import forms


class OrganizationMembershipInline(admin.TabularInline):
    """
    Inline admin to manage organization members directly from the Organization page.
    """

    model = OrganizationMembership
    extra = 1  # Allows adding new members inline
    autocomplete_fields = ["user"]  # Efficient user search


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    """
    Admin panel for managing user memberships in organizations.
    """

    list_display = ("user", "organization", "role", "joined_at")
    search_fields = ("user__email", "organization__name")
    list_filter = ("role", "joined_at")
    ordering = ("-joined_at",)
    autocomplete_fields = ["user", "organization"]


class OrganizationAdminForm(forms.ModelForm):
    """
    Custom form for Organization to prevent invalid memberships.
    """

    class Meta:
        model = Organization
        fields = "__all__"


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """
    Admin panel for Organization model.
    """

    list_display = ("name", "owner", "created_at")
    search_fields = ("name", "owner__email", "owner__username")
    list_filter = ("created_at",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    inlines = [OrganizationMembershipInline]  # Add the inline

    def save_model(self, request, obj, form, change):
        """
        Validate constraints before saving.
        """
        if not obj.pk:
            super().save_model(request, obj, form, change)  # Save first

        obj.clean()
        super().save_model(request, obj, form, change)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin for User model with additional fields showing organization info.
    """

    list_display = (
        "email",
        "username",
        "phone_number",
        "is_staff",
        "is_active",
    )
    list_filter = ("is_staff", "is_active", "groups")
    search_fields = (
        "email",
        "username",
        "phone_number",
        "owned_organization__name",
        "organization__name",
    )
    ordering = ("-created",)
    readonly_fields = (
        "created",
        "updated",
        "get_organization",
    )  # Make organization info read-only

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Personal Info", {"fields": ("phone_number",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Groups and Permissions", {"fields": ("groups", "user_permissions")}),
        (
            "Organization",
            {"fields": ("get_organization",)},
        ),  # New section for organization info
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

    def get_organization(self, obj):
        """
        Returns the organization the user is associated with.
        If they own an organization, it returns that.
        Otherwise, it returns the first organization they belong to as a member.
        """
        if hasattr(obj, "owned_organization") and obj.owned_organization:
            return f"Owner of {obj.owned_organization.name}"
        elif obj.organization_memberships.exists():  # Check memberships properly
            return f"Member of {obj.organization_memberships.first().organization.name}"
        return "No organization"

    get_organization.short_description = "Organization"
