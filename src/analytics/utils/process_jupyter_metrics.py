import base64
import uuid
import os
from django.core.files.base import ContentFile, File
from django.core.files.storage import default_storage
from django.db import transaction
from analytics.models import Metric
from .jupyter_parser import parse_jupyter_html


def process_jupyter_metrics(html_file, report, upload=None, file_entries=None):
    """
    Procesa un archivo HTML exportado de Jupyter Notebook y registra las métricas encontradas.
    - Idempotente a nivel (report, upload): limpia métricas previas de preview para esa versión antes de insertar.
    - Soporta KPIs, texto, gráficas (base64) y tablas (vinculadas a archivos complementarios).

    Retorna:
        tuple: (metric_count, processed_tables)
            - metric_count: Número de métricas guardadas
            - processed_tables: Conjunto de NOMBRES ORIGINALES normalizados de tablas procesadas
                                (para evitar reinsertarlas como complementarios en la task).
    """
    # Lee el HTML
    content = html_file.read()

    # Normalizador
    def _norm_base(s):
        return os.path.basename((s or "")).strip().lower()

    # Archivos complementarios
    file_entries = file_entries or []
    file_map = {e["original_name"]: e["stored_path"] for e in file_entries}
    # 👇 clave del fix: mapa inverso para recuperar el nombre ORIGINAL desde el stored_path
    stored_to_original = {e["stored_path"]: e["original_name"] for e in file_entries}

    # Ejecuta el parser
    results, _ = parse_jupyter_html(content, file_map=file_map)

    # Mapa de tipos del parser -> modelo
    type_map = {
        "kpi": "single_value",
        "text": "text",
        "chart": "plot",
        "table": "table",
    }

    # Para devolver a la task (nombres ORIGINALES normalizados)
    processed_tables = set()

    # Dedupe defensivo local de tablas por path y basename
    seen_table_basenames = set()
    seen_table_paths = set()

    metric_count = 0

    with transaction.atomic():
        # Idempotencia: limpia métricas preview previas de esa versión
        if upload is not None:
            Metric.objects.filter(
                report=report, source_upload=upload, is_preview=True
            ).delete()
        else:
            Metric.objects.filter(
                report=report, source_upload__isnull=True, is_preview=True
            ).delete()

        # Inserción ordenada según el parser
        for i, block in enumerate(results):
            m_type = block.get("type")
            model_type = type_map.get(m_type)
            if not model_type:
                continue

            title = (block.get("title") or "").strip() or model_type.title()
            value = block.get("value") or block.get("text")

            print(f"📌 Parsed metric: type={m_type}, title={title}")

            metric = Metric(
                report=report,
                source_upload=upload,
                type=model_type,
                name=title[:255],
                value=value,
                position=i,
                is_preview=True,
            )

            # Charts (base64)
            if m_type == "chart" and block.get("image_base64"):
                try:
                    raw = block["image_base64"]
                    b64_payload = raw.split(",", 1)[-1] if "," in raw else raw
                    image_bytes = base64.b64decode(b64_payload)
                    metric.file.save(
                        f"{uuid.uuid4().hex}.png", ContentFile(image_bytes), save=False
                    )
                except Exception as e:
                    print(f"⚠️ Chart decode failed for '{title}': {e}")

            # Tablas (desde storage)
            elif m_type == "table" and block.get("file_path"):
                path = block["file_path"]
                base = _norm_base(path)

                # Dedupe local
                if base in seen_table_basenames or path in seen_table_paths:
                    print(f"↩️ Skipping duplicated table: base='{base}' path='{path}'")
                else:
                    try:
                        with default_storage.open(path, "rb") as f:
                            metric.file.save(
                                os.path.basename(path), File(f), save=False
                            )

                        seen_table_basenames.add(base)
                        seen_table_paths.add(path)

                        # ✅ Añade el NOMBRE ORIGINAL normalizado si lo conocemos;
                        #    si no, cae a basename del stored_path.
                        original = stored_to_original.get(path)
                        if original:
                            processed_tables.add(_norm_base(original))
                        else:
                            processed_tables.add(_norm_base(os.path.basename(path)))

                    except Exception as e:
                        print(f"⚠️ Table file missing or unreadable '{path}': {e}")

            # Guarda la métrica
            metric.save()
            metric_count += 1

    return metric_count, processed_tables
