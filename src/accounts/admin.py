from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from accounts.models import User, Organization
from django.core.exceptions import ValidationError
from django import forms


class OrganizationAdminForm(forms.ModelForm):
    """
    Custom form for Organization to handle ManyToMany user relationships properly.
    """

    class Meta:
        model = Organization
        fields = "__all__"

    def clean_users(self):
        """
        Ensure users belong to only one organization and are not also owners.
        """
        users = self.cleaned_data.get("users", [])
        owner = self.cleaned_data.get("owner")

        for user in users:
            if (
                Organization.objects.exclude(id=self.instance.id)
                .filter(users=user)
                .exists()
            ):
                raise ValidationError(
                    f"User {user.username} is already a member of another organization."
                )

            if Organization.objects.filter(owner=user).exists():
                raise ValidationError(
                    f"User {user.username} is an owner of another organization."
                )

            if user == owner:
                raise ValidationError(
                    f"Owner {user.username} should not be in the members list."
                )

        return users


class OrganizationUserInline(admin.TabularInline):
    """
    Inline admin to allow bulk user assignments to organizations.
    Users can be searched dynamically instead of using a dropdown.
    """

    model = Organization.users.through  # Directly references the M2M relation
    extra = 1
    autocomplete_fields = ["user"]  # Allows searching for users by name or email


class OrganizationAdmin(admin.ModelAdmin):
    """
    Admin panel for Organization model with optimized user management.
    """

    form = OrganizationAdminForm
    list_display = ("name", "owner", "created_at")
    search_fields = ("name", "owner__email", "owner__username")
    list_filter = ("created_at",)
    ordering = ("-created_at",)

    # Optimized Fields
    raw_id_fields = ("owner",)  # Efficient owner selection
    autocomplete_fields = ["users"]  # Allows user search instead of dropdown

    # Add users as an inline model for bulk addition
    inlines = [OrganizationUserInline]

    fieldsets = (
        (None, {"fields": ("name", "owner", "users")}),
        ("Metadata", {"fields": ("created_at",)}),
    )
    readonly_fields = ("created_at",)

    def save_model(self, request, obj, form, change):
        """
        Save the Organization instance before adding users.
        """
        if not obj.pk:
            super().save_model(request, obj, form, change)  # Save first to get an ID

        try:
            obj.clean()  # Validate constraints
        except ValidationError as e:
            form.add_error(None, e)
            return

        super().save_model(request, obj, form, change)  # Save again after validation


admin.site.register(Organization, OrganizationAdmin)


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
        Otherwise, it returns the first organization they belong to.
        """
        if hasattr(obj, "owned_organization"):  # User is an owner
            return f"Owner of {obj.owned_organization.name}"
        elif obj.organization.exists():  # User is a member
            return f"Member of {obj.organization.first().name}"
        return "No organization"

    get_organization.short_description = "Organization"
