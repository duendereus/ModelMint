from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from accounts.models import Organization
from labs.models import LabNotebook
from labs.utils.utils import validate_html_file_extension


class LabNotebookAdminForm(forms.ModelForm):
    class Meta:
        model = LabNotebook
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organization"].queryset = Organization.objects.filter(type="lab")


class LabNotebookUploadForm(forms.ModelForm):
    class Meta:
        model = LabNotebook
        fields = ["title", "description", "file", "is_public", "expires_after_hours"]
        widgets = {
            "description": CKEditor5Widget(config_name="default"),
            "expires_after_hours": forms.NumberInput(attrs={"min": 1}),
        }

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop("organization", None)
        created_by = kwargs.pop("created_by", None)
        super().__init__(*args, **kwargs)

        if self.instance:
            self.instance.organization = organization
            self.instance.created_by = created_by

        self.fields["file"].validators.append(validate_html_file_extension)


class NotebookAccessForm(forms.ModelForm):
    allowed_emails_text = forms.CharField(
        label="Allowed emails",
        widget=forms.Textarea(
            attrs={"rows": 6, "placeholder": "Enter one email per line."}
        ),
        required=False,
        help_text="Users will receive a link with OTP access. One email per line.",
    )

    class Meta:
        model = LabNotebook
        fields = ["is_public", "allowed_emails_text", "expires_after_hours"]
        widgets = {
            "expires_after_hours": forms.NumberInput(attrs={"min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Pre-fill allowed_emails_text from instance if available
        if self.instance and self.instance.allowed_emails:
            self.fields["allowed_emails_text"].initial = "\n".join(
                self.instance.allowed_emails
            )

    def clean_allowed_emails_text(self):
        raw = self.cleaned_data["allowed_emails_text"]
        return [email.strip() for email in raw.splitlines() if email.strip()]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.allowed_emails = self.cleaned_data["allowed_emails_text"]
        if commit:
            instance.save()
        return instance
