import base64
import uuid
import os
from django.core.files.base import ContentFile, File
from django.core.files.storage import default_storage
from analytics.models import Metric
from .jupyter_parser import parse_jupyter_html


def process_jupyter_metrics(html_file, report, upload=None, file_entries=None):
    """
    Procesa un archivo HTML generado desde un Jupyter
    Notebook y registra las métricas encontradas.
    Soporta KPIs, texto, gráficas y tablas vinculadas a archivos complementarios.

    Retorna:
        tuple: (metric_count, processed_tables)
            - metric_count: Número de métricas guardadas
            - processed_tables: Lista de nombres originales de tablas procesadas (normalizados)
    """
    content = html_file.read()
    file_map = {
        entry["original_name"]: entry["stored_path"] for entry in (file_entries or [])
    }

    results, _ = parse_jupyter_html(content, file_map=file_map)
    metric_count = 0
    processed_tables = set()

    type_map = {
        "kpi": "single_value",
        "text": "text",
        "chart": "plot",
        "table": "table",
    }

    for i, block in enumerate(results):
        m_type = block["type"]
        title = block["title"]
        model_type = type_map.get(m_type)

        if not model_type:
            continue

        print(f"📌 Parsed metric: type={m_type}, title={title}")

        metric = Metric(
            report=report,
            source_upload=upload,
            type=model_type,
            name=title,
            value=block.get("value") or block.get("text"),
            position=i,
        )

        if m_type == "chart" and "image_base64" in block:
            image_data = block["image_base64"].split(",")[-1]
            file_name = f"{uuid.uuid4().hex}.png"
            metric.file.save(file_name, ContentFile(base64.b64decode(image_data)))

        elif m_type == "table" and "file_path" in block:
            with default_storage.open(block["file_path"], "rb") as f:
                metric.file.save(
                    os.path.basename(block["file_path"]),
                    File(f, name=os.path.basename(block["file_path"])),
                )
            # Guardamos el nombre base normalizado
            processed_tables.add(os.path.basename(block["file_path"]).strip().lower())

        metric.save()
        metric_count += 1

    return metric_count, processed_tables
