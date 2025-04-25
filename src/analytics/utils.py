import os
from django.core.exceptions import ValidationError

# import pandas as pd


def validate_file_extension(value):
    """
    Ensures the uploaded file has a .csv or .xlsx extension.
    """
    ext = os.path.splitext(value.name)[1]  # Get file extension
    valid_extensions = [".csv", ".xlsx"]
    if ext.lower() not in valid_extensions:
        raise ValidationError("Only .csv and .xlsx files are allowed.")


def upload_to_data_file(instance, filename):
    """
    Dynamically sets the upload path to include the organization's name.
    Example: uploads/{org_name}/data/file.csv
    """
    org_name = instance.organization.name.lower().replace(" ", "_")
    return f"uploads/{org_name}/data/{filename}"


def upload_to_metric(instance, filename):
    """
    Sets the upload path for processed metric files.
    Example: uploads/{org_name}/data/{dataset_name}/metrics/{metric_name}/{filename}
    """
    org_name = instance.dataset.organization.name.lower().replace(" ", "_")
    dataset_name = instance.dataset.name.lower().replace(" ", "_")
    metric_name = instance.name.lower().replace(" ", "_")

    # Ensure filename is unique
    base, ext = os.path.splitext(filename)
    new_filename = f"{base}_{instance.id}{ext}" if instance.id else filename

    return (
        f"uploads/{org_name}/data/{dataset_name}/metrics/{metric_name}/{new_filename}"
    )
