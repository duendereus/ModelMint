from django.db import migrations
import django.utils.timezone


def migrate_metrics_to_reports(apps, schema_editor):
    Metric = apps.get_model("analytics", "Metric")
    Report = apps.get_model("analytics", "Report")
    DataSet = apps.get_model("analytics", "DataSet")
    DataUpload = apps.get_model("analytics", "DataUpload")

    from collections import defaultdict

    now = django.utils.timezone.now()

    # ✅ Previene duplicación si ya se aplicó antes
    if Report.objects.filter(title="Migrated Report").exists():
        print("✅ Metrics already migrated. Skipping...")
        return

    # Agrupar métricas antiguas por dataset
    dataset_metrics = defaultdict(list)
    for metric in Metric.objects.filter(report__isnull=True):
        dataset_id = metric.source_upload.dataset_id if metric.source_upload else None
        if dataset_id:
            dataset_metrics[dataset_id].append(metric)

    for dataset_id, metrics in dataset_metrics.items():
        dataset = DataSet.objects.get(id=dataset_id)

        # Buscar el upload más reciente usado para procesamiento
        latest_upload = (
            DataUpload.objects.filter(dataset=dataset, used_for_processing=True)
            .order_by("-version", "-created_at")
            .first()
        )

        report = Report.objects.create(
            dataset=dataset,
            title="Migrated Report",
            description="Auto-generated from pre-refactor metrics.",
            upload=latest_upload,
            created_by=dataset.created_by,
            created_at=now,
            processed=True,
        )

        for metric in metrics:
            metric.report_id = report.id
            metric.save(update_fields=["report"])


def reverse_migration(apps, schema_editor):
    # No reverse logic
    pass


class Migration(migrations.Migration):

    dependencies = [
        (
            "analytics",
            "0009_alter_metric_options_remove_jupyterreport_dataset_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(migrate_metrics_to_reports, reverse_migration),
    ]
