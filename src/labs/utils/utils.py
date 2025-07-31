import os, uuid
from django.utils.text import slugify
from datetime import datetime
from django.core.exceptions import ValidationError


def upload_to_lab_notebook(instance, filename):
    """
    Generates a unique upload path for LabNotebook and NotebookVersion files.
    """

    # Handle both models: LabNotebook and NotebookVersion
    if hasattr(instance, "notebook"):
        notebook = instance.notebook
    else:
        notebook = instance

    org_slug = slugify(notebook.organization.name)[:20]
    notebook_slug = slugify(notebook.slug)[:30]

    base, ext = os.path.splitext(filename)
    ext = ext.lower()

    # Slugify filename base
    clean_base = slugify(base)[:50]

    # Add short UUID to prevent overwrite
    unique_suffix = uuid.uuid4().hex[:8]
    final_filename = f"{clean_base}-{unique_suffix}{ext}"

    print(f"[DEBUG] Generating upload path for: {filename} → {final_filename}")
    return f"uploads/lab_notebooks/{org_slug}/{notebook_slug}/{final_filename}"


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
