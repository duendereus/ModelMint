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
    org_name = instance.report.dataset.organization.name.lower().replace(" ", "_")[:20]
    dataset_name = instance.report.dataset.name.lower().replace(" ", "_")[:20]
    metric_name = instance.name.lower().replace(" ", "_")[:20]

    base, ext = os.path.splitext(filename)
    new_filename = f"{base}_{instance.id}{ext}" if instance.id else filename

    return (
        f"uploads/{org_name}/data/{dataset_name}/metrics/{metric_name}/{new_filename}"
    )


def validate_jupyter_extension(value):
    """
    Ensures the uploaded file has a .html extension (Jupyter Notebook export).
    """
    ext = os.path.splitext(value.name)[1].lower()
    if ext != ".html":
        raise ValidationError("Only .html files exported from Jupyter are allowed.")


def upload_to_jupyter_report(instance, filename):
    """
    Stores the Jupyter HTML notebook in:
    uploads/{org_name}/data/jupyter/{filename}
    """
    if instance.report and instance.report.dataset:
        org_name = instance.report.dataset.organization.name.lower().replace(" ", "_")
    else:
        org_name = "unknown_org"
    return f"uploads/{org_name}/data/jupyter/{filename}"


def get_user_organization(user):
    """
    Returns the organization associated with the user, either as owner or member.
    """
    if hasattr(user, "owned_organization") and user.owned_organization:
        return user.owned_organization

    membership = user.organization_memberships.first()
    if membership:
        return membership.organization

    return None


def upload_to_example_file(instance, filename):
    """
    Stores the example file (for dynamic dashboards) in:
    uploads/{org_name}/data/{dataset_name}/reports/examples/{filename}
    """
    if instance.dataset and instance.dataset.organization:
        org_name = instance.dataset.organization.name.lower().replace(" ", "_")[:20]
        dataset_name = instance.dataset.name.lower().replace(" ", "_")[:20]
    else:
        org_name = "unknown_org"
        dataset_name = "unknown_dataset"

    return f"uploads/{org_name}/data/{dataset_name}/reports/examples/{filename}"
