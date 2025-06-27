from django import forms
from accounts.models import Organization
from labs.models import LabNotebook


class LabNotebookAdminForm(forms.ModelForm):
    class Meta:
        model = LabNotebook
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organization"].queryset = Organization.objects.filter(type="lab")
