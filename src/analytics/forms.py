from django import forms
from .models import DataUpload


class DataUploadForm(forms.ModelForm):
    """Form for users to upload files, ensuring organization and user are set correctly."""

    class Meta:
        model = DataUpload
        fields = ["title", "file", "job_instructions"]  # ✅ Only show necessary fields

    def __init__(self, *args, **kwargs):
        """Dynamically set the organization queryset based on the user."""
        self.user = kwargs.pop("user", None)  # Get user from kwargs
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        """Ensure both organization and uploaded_by are set before saving."""
        instance = super().save(commit=False)

        # ✅ Assign `uploaded_by` explicitly
        if not instance.uploaded_by:
            instance.uploaded_by = self.user

        # ✅ Assign organization: Check if user is an owner or a member
        if hasattr(self.user, "owned_organization"):
            instance.organization = self.user.owned_organization
        elif hasattr(self.user, "organization_membership"):
            instance.organization = self.user.organization_membership.organization
        else:
            raise ValueError("User must belong to an organization to upload data.")

        if commit:
            instance.save()
        return instance
