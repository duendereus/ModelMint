import base64
import uuid
from django.core.files.base import ContentFile
from analytics.utils.jupyter_parser import parse_jupyter_html
from labs.models import NotebookMetric


def process_lab_metrics(html_file, notebook, version_obj):
    """
    Procesa un archivo HTML generado desde un Jupyter Notebook
    y guarda los resultados como métricas del producto Labs
    (en la versión específica del notebook).
    """
    content = html_file.read()
    results = parse_jupyter_html(content)
    metric_count = 0

    type_map = {
        "kpi": "single_value",
        "text": "text",
        "chart": "plot",
    }

    for i, block in enumerate(results):
        m_type = block["type"]
        title = block["title"]
        model_type = type_map.get(m_type)

        if not model_type:
            continue

        metric = NotebookMetric.objects.create(
            notebook=notebook,
            version_obj=version_obj,
            type=model_type,
            name=title,
            value=block.get("value") or block.get("text"),
            position=i,
        )

        if m_type == "chart" and "image_base64" in block:
            image_data = block["image_base64"].split(",")[-1]
            file_name = f"{uuid.uuid4().hex}.png"
            metric.file.save(file_name, ContentFile(base64.b64decode(image_data)))
            metric.save()

        metric_count += 1

    return metric_count
