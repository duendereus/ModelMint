from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from accounts.models import Organization
from labs.models import LabNotebook
from labs.utils import validate_html_file_extension


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
        super().__init__(*args, **kwargs)
        self.fields["file"].validators.append(validate_html_file_extension)
