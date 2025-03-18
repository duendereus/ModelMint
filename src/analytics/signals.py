import os
import pandas as pd
import json
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Metric, TableMetric

@receiver(post_save, sender=Metric)
def process_table_metric(sender, instance, created, **kwargs):
    """
    Signal that processes a CSV/Excel file and stores its contents in TableMetric.
    Runs only for 'table' metrics.
    """
    if instance.type != "table" or not instance.file:
        return  # Exit if not a table metric or no file uploaded

    try:
        # ✅ Open the file properly (handles local & S3)
        with instance.file.open("rb") as file:
            _, file_extension = os.path.splitext(instance.file.name)

            # ✅ Read file based on extension
            if file_extension.lower() == ".csv":
                df = pd.read_csv(file)
            elif file_extension.lower() in [".xls", ".xlsx"]:
                df = pd.read_excel(file)
            else:
                raise ValueError("Invalid file type. Only CSV or Excel files are supported.")

        if df.empty:
            print(f"⚠️ Warning: The file {instance.file.name} is empty.")

        # ✅ Convert all numerical NaN values to None
        df = df.where(pd.notna(df), None)

        # ✅ Ensure all values are JSON-compatible
        df = df.astype(object).where(pd.notna(df), None)

        # ✅ Convert DataFrame to JSON
        table_data = {
            "columns": list(df.columns),
            "data": json.loads(df.to_json(orient="records")),  # Ensures valid JSON
        }

        # ✅ Store in TableMetric
        TableMetric.objects.update_or_create(metric=instance, defaults=table_data)

        print(f"✅ Table data for '{instance.name}' successfully processed and stored.")

    except Exception as e:
        print(f"❌ Error processing table metric '{instance.name}': {str(e)}")
