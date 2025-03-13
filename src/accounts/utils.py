import re
import string
import random
from django.core.exceptions import ValidationError
from django.shortcuts import redirect


def validate_phone_number(value):
    """
    Validates that the phone number starts with an
    optional '+' followed by digits only.
    Spaces are allowed but ignored, and the total number
    of digits (excluding spaces) must be between 10 and 15.
    """
    # Normalize the value by removing spaces
    normalized_value = value.replace(" ", "")

    # Ensure the normalized value matches the pattern
    if not re.fullmatch(r"\+?\d{10,15}", normalized_value):
        raise ValidationError(
            "Phone number must be between 10 and 15 digits and may start with a '+'."
        )

    # Ensure the phone number is not just '+'
    if normalized_value == "+":
        raise ValidationError("Phone number cannot consist of '+' only.")


def custom_password_validator(value):
    """Custom password validator with security rules"""
    if len(value) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not any(char.isdigit() for char in value):
        raise ValidationError("Password must contain at least one digit.")
    if not any(char.isupper() for char in value):
        raise ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\'":\\|,.<>/?]', value):
        raise ValidationError("Password must contain at least one special character.")


def anonymous_required(view_func):
    """Redirect authenticated users away from login/register pages."""

    def wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")  # Redirect logged-in users
        return view_func(request, *args, **kwargs)

    return wrapped_view


def generate_random_password(length=12):
    """Generates a random password."""
    characters = string.ascii_letters + string.digits + string.punctuation
    return "".join(random.choice(characters) for _ in range(length))
