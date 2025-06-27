import os
import pandas as pd
import json
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import NotebookMetric, NotebookTableMetric


@receiver(post_save, sender=NotebookMetric)
def process_lab_table_metric(sender, instance, created, **kwargs):
    """
    Signal that processes a CSV/Excel file uploaded to NotebookMetric of type 'table'.
    Automatically extracts and stores the table content as JSON.
    """
    if instance.type != "table" or not instance.file:
        return  # Skip non-table metrics or missing files

    try:
        with instance.file.open("rb") as file:
            _, file_extension = os.path.splitext(instance.file.name.lower())

            if file_extension == ".csv":
                df = pd.read_csv(file)
            elif file_extension in [".xls", ".xlsx"]:
                df = pd.read_excel(file)
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")

        if df.empty:
            print(f"⚠️ Warning: Uploaded table file for '{instance.name}' is empty.")

        df = df.where(pd.notna(df), None).astype(object)

        table_data = {
            "columns": list(df.columns),
            "data": json.loads(df.to_json(orient="records")),
        }

        NotebookTableMetric.objects.update_or_create(
            metric=instance,
            defaults=table_data,
        )

        print(f"✅ Table data stored for lab metric '{instance.name}'.")

    except Exception as e:
        print(f"❌ Error processing table metric '{instance.name}': {str(e)}")
