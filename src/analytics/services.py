from analytics.models import Report


def mark_as_processed(report: Report):
    """
    Marca un Report como el actual usado para mostrar métricas
    y desactiva todos los anteriores del mismo dataset.
    """
    if not report or not report.dataset:
        raise ValueError("Report and associated dataset are required.")

    # Desactivar anteriores
    Report.objects.filter(dataset=report.dataset).exclude(id=report.id).update(
        processed=False
    )

    # Activar este
    report.processed = True
    report.save()
