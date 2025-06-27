import os
from django.utils.text import slugify
from datetime import datetime
from django.core.exceptions import ValidationError


def upload_to_lab_notebook(instance, filename):
    org_slug = slugify(instance.organization.name)[:20]
    notebook_slug = slugify(instance.slug)[:30]
    ext = os.path.splitext(filename)[1].lower()
    filename = f"notebook{ext}"  # standard filename

    return f"uploads/lab_notebooks/{org_slug}/{notebook_slug}/{filename}"


def validate_html_file_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext != ".html":
        raise ValidationError("Only .html files are supported for Lab Notebooks.")


def upload_to_metric_labs(instance, filename):
    org_slug = slugify(instance.notebook.organization.name)[:20]
    notebook_slug = slugify(instance.notebook.slug)[:30]
    metric_slug = slugify(instance.name)[:30]

    base, ext = os.path.splitext(filename)
    new_filename = f"{metric_slug}_{instance.id}{ext}" if instance.id else filename

    return f"uploads/lab_notebooks/{org_slug}/{notebook_slug}/metrics/{metric_slug}/{new_filename}"
