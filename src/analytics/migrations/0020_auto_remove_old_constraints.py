# analytics/migrations/0020_auto_remove_old_constraints.py

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0019_add_metric_constraint"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="metric",
            unique_together=set(),  # Elimina todos los anteriores
        ),
    ]
