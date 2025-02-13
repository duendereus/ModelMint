import re
from django.core.exceptions import ValidationError


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
