from django import forms
from django.contrib.auth import get_user_model
from accounts.models import OrganizationMembership

User = get_user_model()


class InviteMemberForm(forms.Form):
    email = forms.EmailField()
    role = forms.ChoiceField(choices=OrganizationMembership.ROLE_CHOICES)

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email
