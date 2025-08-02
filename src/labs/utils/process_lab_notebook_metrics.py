import base64
import uuid
import os
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.base import File
from analytics.utils.jupyter_parser import parse_jupyter_html, clean_metric_name
from labs.models import NotebookMetric


def process_lab_metrics(html_file, notebook, version_obj, file_entries=None):
    content = html_file.read()
    file_map = {
        entry["original_name"]: entry["stored_path"] for entry in file_entries or []
    }

    results, _ = parse_jupyter_html(content, file_map=file_map)

    # ✅ DEBUG: Ver orden de aparición antes de crear objetos
    for i, block in enumerate(results):
        print(f"🔢 Order {i}: type={block['type']} title={block['title']}")

    metric_objs = []

    type_map = {
        "kpi": "single_value",
        "text": "text",
        "chart": "plot",
        "table": "table",
    }

    for block in results:
        m_type = block["type"]
        title = block["title"]
        model_type = type_map.get(m_type)

        if not model_type:
            continue

        print(f"📌 Parsed metric: type={m_type}, title={title}")

        metric = NotebookMetric(
            notebook=notebook,
            version_obj=version_obj,
            type=model_type,
            name=title,
            value=block.get("value") or block.get("text"),
        )

        if m_type == "chart" and "image_base64" in block:
            image_data = block["image_base64"].split(",")[-1]
            file_name = f"{uuid.uuid4().hex}.png"
            metric._image_content = (file_name, base64.b64decode(image_data))

        elif m_type == "table" and "file_path" in block:
            metric._table_path = block["file_path"]

        metric_objs.append(metric)

    # ✅ Guardar todos los objetos y luego aplicar sus archivos
    for i, metric in enumerate(metric_objs):
        metric.position = i
        metric.save()

        if hasattr(metric, "_image_content"):
            fname, content = metric._image_content
            metric.file.save(fname, ContentFile(content))
            metric.save()

        elif hasattr(metric, "_table_path"):
            with default_storage.open(metric._table_path, "rb") as f:
                metric.file.save(
                    os.path.basename(metric._table_path),
                    File(f, name=os.path.basename(metric._table_path)),
                )
                metric.save()

    print(
        f"✅ {len(metric_objs)} total metrics stored for {notebook.title} (v{version_obj.version})"
    )
    return len(metric_objs)
