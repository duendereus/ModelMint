from django.db import migrations, models
import django.db.models.constraints


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0018_alter_report_example_file"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="metric",
            constraint=models.UniqueConstraint(
                fields=["report", "source_upload", "position"],
                name="unique_metric_position_per_upload",
            ),
        ),
    ]
