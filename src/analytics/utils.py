import os
from django.core.exceptions import ValidationError


def validate_file_extension(value):
    """
    Ensures the uploaded file has a .csv or .xlsx extension.
    """
    ext = os.path.splitext(value.name)[1]  # Get file extension
    valid_extensions = [".csv", ".xlsx"]
    if ext.lower() not in valid_extensions:
        raise ValidationError("Only .csv and .xlsx files are allowed.")


def upload_to(instance, filename):
    """
    Dynamically sets the upload path to include the organization's name.
    Example: uploads/{org_name}/data/file.csv
    """
    org_name = instance.organization.name.lower().replace(" ", "_")
    return f"uploads/{org_name}/data/{filename}"
