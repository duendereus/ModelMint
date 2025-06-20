import base64
import uuid
from django.core.files.base import ContentFile
from analytics.models import Metric
from .jupyter_parser import parse_jupyter_html


def process_jupyter_metrics(html_file, report, upload):
    """
    Procesa un archivo HTML generado desde un
    Jupyter Notebook y registra las métricas encontradas.
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

        metric = Metric.objects.create(
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
            metric.save()

        metric_count += 1

    return metric_count
