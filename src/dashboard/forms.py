from django import forms
from django.contrib.auth import get_user_model
from accounts.models import OrganizationMembership

User = get_user_model()


class InviteMemberForm(forms.Form):
    """
    Form to invite a new member to an organization.
    """

    name = forms.CharField(
        max_length=255,
        required=True,
        label="Full Name",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Enter full name"}
        ),
    )
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "Enter email"}
        ),
    )
    role = forms.ChoiceField(
        choices=OrganizationMembership.ROLE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def clean_email(self):
        """
        Ensures that the email is unique in the database.
        """
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email
