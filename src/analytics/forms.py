from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.widgets import CKEditor5Widget
from .models import DataSet, DataUpload, Report


class DataUploadForm(forms.ModelForm):
    class Meta:
        model = DataUpload
        fields = [
            "drive_link",
            "operation",
            "dataset",
        ]


class ReportRequestForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["dataset", "title", "description", "type", "example_file"]
        widgets = {
            "description": CKEditor5Widget(
                attrs={"class": "django_ckeditor_5"}, config_name="default"
            ),
            "type": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop("organization", None)
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["dataset"].queryset = DataSet.objects.filter(
                organization=organization
            )

        self.fields["example_file"].required = False

    def clean(self):
        cleaned_data = super().clean()
        report_type = cleaned_data.get("type")
        example_file = cleaned_data.get("example_file")

        if report_type == "dynamic" and not example_file:
            self.add_error(
                "example_file",
                ValidationError(
                    _("This field is required for dynamic dashboards."),
                    code="required",
                ),
            )
        return cleaned_data
