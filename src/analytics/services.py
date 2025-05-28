from .models import DataUpload


def mark_as_processed(upload: DataUpload):
    """
    Marca un DataUpload como el actual usado para procesar métricas
    y desactiva todos los anteriores.
    """
    if not upload or not upload.dataset:
        raise ValueError("Upload and associated dataset are required.")

    # Desactivar los anteriores
    DataUpload.objects.filter(dataset=upload.dataset).exclude(id=upload.id).update(
        used_for_processing=False
    )

    # Activar el actual
    upload.used_for_processing = True
    upload.removed = False
    upload.save()
