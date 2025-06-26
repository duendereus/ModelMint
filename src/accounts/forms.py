from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from .models import Organization, UserProfile
from .utils import custom_password_validator

User = get_user_model()


class UserRegistrationForm(forms.ModelForm):
    """Form to handle user registration"""

    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Password"}),
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm Password"}),
    )
    organization_name = forms.CharField(
        label="Organization Name",
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Company/Project Name"}),
    )

    class Meta:
        model = User
        fields = ["username", "email"]

    def clean_email(self):
        email = self.cleaned_data.get("email")
        validate_email(email)
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords do not match.")

        # Validate organization uniqueness
        org_name = cleaned_data.get("organization_name")
        if Organization.objects.filter(name=org_name).exists():
            raise ValidationError(
                "This organization name is already taken. Please choose another."
            )

        return cleaned_data

    def save(self, commit=True, org_type="client"):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.is_active = False  # Require email verification

        if commit:
            user.save()  # Save user first to get an ID

            # Create a new organization (ensured unique in clean())
            organization = Organization.objects.create(
                name=self.cleaned_data["organization_name"],
                owner=user,
                type=org_type,  # 👈 Aquí está la diferencia clave
            )

            # The owner should **not** be a member
            # Users should be added to `users` only when necessary
            organization.save()

        return user


class CustomPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "Enter your email"}
        ),
    )

    def clean_email(self):
        email = self.cleaned_data["email"]
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                "If an account is associated with the specified email, "
                "check your inbox to reset your password"
            )
        return email


class CustomSetPasswordForm(SetPasswordForm):
    """
    Custom SetPasswordForm that reuses the custom password validator.
    """

    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "New Password"}),
        label="New Password",
        validators=[custom_password_validator],  # Apply custom validator here
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm New Password"}),
        label="Confirm New Password",
    )


class UserForm(forms.ModelForm):
    """
    Form to update User basic information.
    """

    class Meta:
        model = User
        fields = ["username", "email", "phone_number"]
        widgets = {
            "username": forms.TextInput(
                attrs={"class": "form-control", "readonly": "readonly"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "readonly": "readonly"}
            ),
            "phone_number": forms.TextInput(attrs={"class": "form-control"}),
        }


class UserProfileForm(forms.ModelForm):
    """
    Form to update User Profile information.
    """

    class Meta:
        model = UserProfile
        fields = ["name", "profile_picture", "job_title", "bio", "linkedin"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "job_title": forms.TextInput(attrs={"class": "form-control"}),
            "bio": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "linkedin": forms.URLInput(attrs={"class": "form-control"}),
        }
