from django import forms
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
        fields = ["dataset", "title", "description"]
        widgets = {
            "description": CKEditor5Widget(
                attrs={"class": "django_ckeditor_5"}, config_name="default"
            ),
        }

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop("organization", None)
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["dataset"].queryset = DataSet.objects.filter(
                organization=organization
            )
