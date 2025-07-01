from celery import shared_task
from bs4 import BeautifulSoup
from labs.models import LabNotebook, NotebookMetric
from labs.utils.jupyter_parser import extract_kpis, extract_charts, extract_text_blocks
import os, io


@shared_task
def process_lab_notebook_task(notebook_id):
    try:
        notebook = LabNotebook.objects.select_related("organization").get(
            id=notebook_id
        )

        # ✅ Abrir el archivo HTML como texto con utf-8
        with notebook.file.open("rb") as f:
            html = io.TextIOWrapper(f, encoding="utf-8").read()

        soup = BeautifulSoup(html, "html.parser")

        # 📌 Definir versión nueva
        last_metric = notebook.metrics.order_by("-version").first()
        version = last_metric.version + 1 if last_metric else 1
        position = 0

        # ✅ Extraer y guardar KPIs
        for metric in extract_kpis(soup):
            NotebookMetric.objects.create(
                notebook=notebook,
                version=version,
                type="kpi",
                name=metric["name"],
                value=metric["value"],
                position=position,
            )
            position += 1

        # ✅ Extraer y guardar gráficas
        for metric in extract_charts(soup):
            NotebookMetric.objects.create(
                notebook=notebook,
                version=version,
                type="chart",
                name=metric["name"],
                value=None,
                file=None,
                position=position,
            )
            position += 1

        # ✅ Extraer y guardar bloques de texto
        for metric in extract_text_blocks(soup):
            NotebookMetric.objects.create(
                notebook=notebook,
                version=version,
                type="text",
                name=metric["name"],
                value=metric["value"],
                position=position,
            )
            position += 1

        # ✅ Agregar archivos complementarios como métricas tipo "table"
        from labs.models import NotebookTableMetric

        tables = NotebookTableMetric.objects.filter(
            metric__notebook=notebook
        ).select_related("metric")

        for table in tables:
            metric = table.metric
            # Solo crear si aún no tiene métrica
            if not metric:
                table_name = (
                    os.path.splitext(table.original_filename)[0]
                    .replace("_", " ")
                    .title()
                )
                NotebookMetric.objects.create(
                    notebook=notebook,
                    version=version,
                    type="table",
                    name=table_name[:255],
                    file=table.file,
                    value=None,
                    position=position,
                )
                position += 1

        print(
            f"✅ Processed notebook '{notebook.title}' with {position} metrics (v{version})."
        )
        return f"Processed notebook {notebook_id} with {position} metrics."

    except Exception as e:
        print(f"❌ Error processing notebook {notebook_id}: {str(e)}")
        return f"Error: {str(e)}"
