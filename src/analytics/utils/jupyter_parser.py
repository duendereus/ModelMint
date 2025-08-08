from bs4 import BeautifulSoup, Comment
import re
import unicodedata
import os
import logging

log = logging.getLogger(__name__)

# -----------------------
# Utilidades y constantes
# -----------------------
NBSP = "\xa0"
MAX_TITLE_LEN = 140

ANCHOR_LINK_RE = re.compile(r"<a[^>]+anchor-link[^>]*>.*?</a>", re.I | re.S)
TO_EXPORT_RE = re.compile(r'to_(csv|excel)\(["\'](.+?)["\']', re.I)


def clean_text_basic(text):
    return (
        "".join(c for c in text if unicodedata.category(c)[0] != "C")
        .replace("\u2029", "")
        .replace("\xa0", " ")
        .replace("\u200b", "")
        .replace("¶", "")
        .strip()
    )


def clean_text_rich(text):
    cleaned = (
        "".join(c for c in text if unicodedata.category(c)[0] != "C")
        .replace("\u2029", "\n")
        .replace("\xa0", " ")
        .replace("\u200b", "")
        .replace("¶", "\n")
        .strip()
    )
    return cleaned


def infer_metric_type(label):
    label = label.lower()
    if "kpi" in label:
        return "kpi"
    elif any(word in label for word in ["chart", "plot", "image", "graph"]):
        return "chart"
    return "text"


def parse_mint_comment(comment):
    match = re.match(r"Mint it:\s*(.+)", comment.strip(), re.IGNORECASE)
    if not match:
        return None
    raw_parts = [p.strip() for p in match.group(1).split("|")]
    metadata = {"type": infer_metric_type(raw_parts[0])}
    for part in raw_parts[1:]:
        if "=" in part:
            key, val = part.split("=", 1)
            key = key.strip().lower()
            val = clean_text_rich(val.strip())
            metadata[key] = val
            if key == "title":
                metadata["titles"] = [clean_text_rich(t) for t in val.split(";")]
    return metadata


def is_probably_junk(text):
    text = text.strip().lower()
    if not text:
        return True
    if any(
        x in text
        for x in ["rangeindex", "dtype", "memory usage", "<axes", "datetime64"]
    ):
        return True
    if re.fullmatch(r"\d{2}:\d{2}(\.\d+)?", text):
        return True
    if re.fullmatch(r"\d{2}:\d{2}:\d{2}(\.\d+)?", text):
        return True
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2}(\.\d+)?)?)?", text):
        return True
    return False


def find_plt_title_upwards_only(el):
    def extract_title_from_code(text):
        patterns = [
            r'plt\.title\(\s*["\'](.*?)["\']\s*\)',
            r'ax\.set_title\(\s*["\'](.*?)["\']\s*[,)]',
            r'fig\.suptitle\(\s*["\'](.*?)["\']\s*[,)]',
            r"title\s*=\s*\{[\"']center[\"']:\s*[\"'](.*?)[\"']\}",
        ]
        for pattern in patterns:
            try:
                matches = re.findall(pattern, text)
                if matches:
                    for t in matches:
                        cleaned = clean_text_rich(t)
                        if not is_probably_junk(cleaned):
                            return cleaned
            except re.error:
                continue
        return None

    visited = set()
    node = el
    for _ in range(10):
        if not node or node in visited:
            break
        visited.add(node)

        if hasattr(node, "get_text"):
            candidate = extract_title_from_code(node.get_text())
            if candidate:
                return candidate

        if getattr(node, "name", None) == "div" and "output_html" in (
            node.get("class") or []
        ):
            inner_text = clean_text_rich(node.get_text(strip=True))
            if not is_probably_junk(inner_text) and len(inner_text) > 5:
                return inner_text

        node = getattr(node, "parent", None)

    heading = el.find_previous(["h1", "h2", "h3", "strong", "p"])
    if heading:
        htext = clean_text_rich(heading.get_text(strip=True))
        if not is_probably_junk(htext) and len(htext) > 5:
            return htext

    if getattr(el, "name", None) == "img":
        alt_text = el.get("alt")
        if alt_text and not is_probably_junk(alt_text):
            return clean_text_rich(alt_text)

    return None


def clean_metric_name(fname):
    name = os.path.splitext(os.path.basename(fname))[0]
    if re.match(r"^[a-f0-9]{32}_", name):
        name = "_".join(name.split("_")[1:])
    return name.replace("_", " ").title()


# -----------------------
# Ubicar celdas y prompts
# -----------------------
PROMPT_RE = re.compile(r"\[(\d+)\]")
ABOVE_HINT_RE = re.compile(r"\b(above|arriba)\b", re.I)
BELOW_HINT_RE = re.compile(r"\b(below|abajo)\b", re.I)


def _extract_prompt_number(node):
    if not node:
        return None
    txt = node.get_text(separator=" ", strip=True).replace(NBSP, " ")
    m = re.search(r"\b(?:In|Out)?\s*\[(\d+)\]:?", txt)
    return int(m.group(1)) if m else None


def _find_any_prompt_number(cell):
    if not cell:
        return None
    p = cell.find("div", class_="jp-InputPrompt")
    n = _extract_prompt_number(p)
    if n is not None:
        return n
    p = cell.find("div", class_="jp-OutputPrompt")
    n = _extract_prompt_number(p)
    if n is not None:
        return n
    return None


def _nearest_number_in_siblings(cell, prefer="auto", max_hops=15):
    if prefer == "auto":
        md_text = ""
        md = cell.find("div", class_="jp-RenderedMarkdown") if cell else None
        if md:
            md_text = md.get_text(separator=" ", strip=True)
        if ABOVE_HINT_RE.search(md_text):
            prefer = "prev"
        elif BELOW_HINT_RE.search(md_text):
            prefer = "next"
        else:
            prefer = "nearest"

    prev_ptr = cell
    next_ptr = cell
    for hop in range(1, max_hops + 1):
        if prev_ptr is not None:
            prev_ptr = prev_ptr.previous_sibling
            while prev_ptr is not None and (
                getattr(prev_ptr, "name", None) != "div"
                or "jp-Cell" not in (prev_ptr.get("class") or [])
            ):
                prev_ptr = prev_ptr.previous_sibling
            if prev_ptr is not None:
                n = _find_any_prompt_number(prev_ptr)
                if n is not None:
                    if prefer in ("prev", "nearest"):
                        return n
                    prev_candidate = (hop, n)
                else:
                    prev_candidate = locals().get("prev_candidate")

        if next_ptr is not None:
            next_ptr = next_ptr.next_sibling
            while next_ptr is not None and (
                getattr(next_ptr, "name", None) != "div"
                or "jp-Cell" not in (next_ptr.get("class") or [])
            ):
                next_ptr = next_ptr.next_sibling
            if next_ptr is not None:
                n = _find_any_prompt_number(next_ptr)
                if n is not None:
                    if prefer in ("next", "nearest"):
                        return n
                    next_candidate = (hop, n)
                else:
                    next_candidate = locals().get("next_candidate")

        if (
            prefer == "prev"
            and "prev_candidate" in locals()
            and locals()["prev_candidate"][0] == hop
        ):
            return locals()["prev_candidate"][1]
        if (
            prefer == "next"
            and "next_candidate" in locals()
            and locals()["next_candidate"][0] == hop
        ):
            return locals()["next_candidate"][1]

    pc = locals().get("prev_candidate")
    nc = locals().get("next_candidate")
    if pc and nc:
        return pc[1] if pc[0] <= nc[0] else nc[1]
    if pc:
        return pc[1]
    if nc:
        return nc[1]
    return None


def find_nearest_cell_number(el, fallback_counter=[0], max_hops=15, _cache=None):
    # memo
    if _cache is not None:
        key = id(el)
        if key in _cache:
            return _cache[key]

    if el is None:
        fallback_counter[0] += 1
        val = 8000 + fallback_counter[0]
        if _cache is not None:
            _cache[key] = val
        return val

    cell = el
    while cell and not (
        getattr(cell, "name", None) == "div" and "jp-Cell" in (cell.get("class") or [])
    ):
        cell = getattr(cell, "parent", None)

    n = _find_any_prompt_number(cell)
    if n is None:
        n = _nearest_number_in_siblings(cell, prefer="auto", max_hops=max_hops)

    if n is None:
        prev_prompt = el.find_previous(
            "div", class_=["jp-InputPrompt", "jp-OutputPrompt"]
        )
        n = _extract_prompt_number(prev_prompt)
    if n is None:
        next_prompt = el.find_next("div", class_=["jp-InputPrompt", "jp-OutputPrompt"])
        n = _extract_prompt_number(next_prompt)
    if n is None:
        fallback_counter[0] += 1
        n = 8000 + fallback_counter[0]

    if _cache is not None:
        _cache[key] = n
    return n


def find_cell_number_for_element(el):
    parent = el
    jp_cell = None
    while parent:
        if (
            getattr(parent, "name", None) == "div"
            and any(c.startswith("jp-Cell") for c in (parent.get("class") or []))
            and not any(
                sub in c
                for c in (parent.get("class") or [])
                for sub in ["outputArea", "inputArea", "outputWrapper"]
            )
        ):
            jp_cell = parent
            break
        parent = getattr(parent, "parent", None)

    if not jp_cell:
        return 9997

    prompt_el = jp_cell.find("div", class_="jp-InputPrompt")
    if prompt_el:
        text = prompt_el.get_text().replace(NBSP, " ").strip()
        m = re.match(r"In\s*\[(\d+)\]:?", text)
        if m:
            return int(m.group(1))
    return 9997


def _build_markdown_cell(soup, html_string, anchor_value):
    outer = soup.new_tag(
        "div",
        **{
            "class": "jp-Cell jp-MarkdownCell jp-Notebook-cell",
            "data-lab-anchor": anchor_value,
        },
    )
    iw = soup.new_tag("div", **{"class": "jp-Cell-inputWrapper"})
    outer.append(iw)
    input_area = soup.new_tag("div", **{"class": "jp-InputArea jp-Cell-inputArea"})
    iw.append(input_area)
    prompt = soup.new_tag("div", **{"class": "jp-InputPrompt jp-InputArea-prompt"})
    input_area.append(prompt)
    md = soup.new_tag(
        "div",
        **{
            "class": "jp-RenderedHTMLCommon jp-RenderedMarkdown jp-MarkdownOutput",
            "data-mime-type": "text/markdown",
        },
    )
    md.append(BeautifulSoup(html_string, "html.parser"))
    input_area.append(md)
    return outer


def _find_cell_by_number(soup, cell_number: int):
    for prompt in soup.find_all("div", class_=["jp-InputPrompt", "jp-OutputPrompt"]):
        txt = prompt.get_text(separator=" ", strip=True).replace(NBSP, " ")
        m = re.search(r"\b(?:In|Out)?\s*\[(\d+)\]:?", txt)
        if m and int(m.group(1)) == cell_number:
            cell = prompt
            while cell and not (
                getattr(cell, "name", None) == "div"
                and "jp-Cell" in (cell.get("class") or [])
            ):
                cell = getattr(cell, "parent", None)
            return cell
    return None


def _insert_markdown_after_cell_number(soup, cell_number, html_string):
    cell = _find_cell_by_number(soup, cell_number)
    if not cell:
        log.warning(
            "[obs] No encontré celda para número %s; no inserto markdown.", cell_number
        )
        return None

    anchor_value = f"obs-{cell_number}"

    nxt = cell.next_sibling
    while nxt is not None and (getattr(nxt, "name", None) != "div"):
        nxt = nxt.next_sibling
    if nxt is not None:
        classes = nxt.get("class") or []
        if (
            "jp-Cell" in classes
            and "jp-MarkdownCell" in classes
            and nxt.get("data-lab-anchor") == anchor_value
        ):
            log.info("[obs] Ya existía comentario debajo de In[%s].", cell_number)
            return nxt

    md_cell = _build_markdown_cell(soup, html_string, anchor_value)
    cell.insert_after(md_cell)
    log.info("[obs] Comentario insertado debajo de In[%s].", cell_number)
    return md_cell


def is_input_prompt(el):
    return (
        getattr(el, "name", None) == "div"
        and "jp-InputPrompt" in (el.get("class") or [])
        and re.search(r"In\s*\[\d+\]", el.get_text())
    )


def is_cell_wrapper(el):
    return getattr(el, "name", None) == "div" and any(
        cls.startswith("jp-Cell") for cls in (el.get("class") or [])
    )


def extract_kpis_from_text(text):
    kpis = []
    for line in text.splitlines():
        if ":" not in line or line.count(":") > 2:
            continue
        title, value = line.split(":", 1)
        title, value = clean_text_basic(title), clean_text_basic(value)
        if len(title) > 80 or (len(value) > 50 and " " in value):
            continue
        if (
            not title
            or not value
            or is_probably_junk(title)
            or is_probably_junk(value)
            or any(
                x in value
                for x in ["{", "}", "return", "=", "def ", "lambda", "(", ")"]
            )
        ):
            continue
        if len(title) > 5 and len(value) < 100:
            kpis.append({"type": "kpi", "title": title, "value": value})
    return kpis


PRINT_LINE_RE = re.compile(
    r"""^\s*(?:[•\-\*\u2022]?\s*)        # bullet opcional
        (?P<title>[^:\n\r]{3,100}?)      # título legible
        \s*[:：]\s*                       # dos puntos (ascii o fullwidth)
        (?P<value>[^\n\r]{1,120})\s*$    # valor corto
    """,
    re.X,
)


def extract_print_block_kpis(text):
    """
    Acepta viñetas y espacios raros. Devuelve [{'type':'kpi','title':..., 'value':...}, ...]
    """
    kpis = []
    for raw in text.splitlines():
        line = clean_text_rich(raw).strip()
        if not line:
            continue
        m = PRINT_LINE_RE.match(line)
        if not m:
            continue
        title = clean_text_basic(m.group("title"))
        value = clean_text_basic(m.group("value"))
        # filtros suaves: evita código o basura
        if is_probably_junk(title) or is_probably_junk(value):
            continue
        if len(title) > 100 or len(value) > 150:
            continue
        # evita capturar líneas de código con '=' o 'def', etc.
        if any(
            x in value for x in ["{", "}", "return", "=", "def ", "lambda", "(", ")"]
        ):
            continue
        kpis.append({"type": "kpi", "title": title, "value": value})
    return kpis


def is_text_output(el):
    if el.name != "div":
        return False
    classes = " ".join(el.get("class") or [])
    # Solo RenderedText o bloques marcados explícitamente como text/plain
    if "RenderedText" in classes:
        return True
    if el.get("data-mime-type") == "text/plain":
        return True
    return False


INFO_DF_RE = re.compile(
    r"^<class\s+'pandas\.core\.frame\.DataFrame'>|^RangeIndex:\s+\d+ entries.*?memory usage:",
    re.IGNORECASE | re.DOTALL,
)

STATSMODELS_SUMMARY_RE = re.compile(
    r"(ExponentialSmoothing|ARIMA|SARIMAX|OLS|Holt).*(Model Results|Results)",
    re.IGNORECASE | re.DOTALL,
)


def is_noise_text_block(raw_text: str) -> bool:
    t = raw_text.strip()
    if not t:
        return True
    if INFO_DF_RE.search(t):
        return True
    if STATSMODELS_SUMMARY_RE.search(t):
        return True
    # opcional: descartar tochos sin bullets ni pares clave:valor
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    has_bullets = any(l.startswith(("•", "-", "*")) for l in lines)
    has_pairs = sum(1 for l in lines if ":" in l) >= 2
    too_long = len(t) > 2000 and not (has_bullets or has_pairs)
    return too_long


# -----------------------
# PARSER PRINCIPAL
# -----------------------
def parse_jupyter_html(
    content, file_map=None, return_modified_html=False, group_print_kpis_mode="auto"
):
    """
    Devuelve:
      - results: lista de artefactos (charts/kpis/text/tables)
      - exported_filenames_order: lista (tal cual)
      - (opcional) html_modificado: str(soup) si return_modified_html=True
    """
    soup = BeautifulSoup(content, "html.parser")

    results = []
    current_metadata = None
    pending_metadata = None
    used_imgs = set()
    used_files = set()
    accumulated_html = []
    exported_filenames_order = []
    current_cell_number = None
    locked_cell_number = None

    nearest_cache = {}

    # --------------------------
    # Helpers locales de orden
    # --------------------------
    dom_seq = 0

    def bump_seq():
        nonlocal dom_seq
        dom_seq += 1
        return dom_seq

    def base_num():
        return current_cell_number if isinstance(current_cell_number, int) else 8000

    def compute_markdown_sort_key(el, fallback_base=None, debug=False):
        prev_p = el.find_previous("div", class_=["jp-InputPrompt", "jp-OutputPrompt"])
        next_p = el.find_next("div", class_=["jp-InputPrompt", "jp-OutputPrompt"])
        prev_n = _extract_prompt_number(prev_p)
        next_n = _extract_prompt_number(next_p)

        if prev_n is not None:
            s_key = float(prev_n) + 0.50
        elif next_n is not None:
            s_key = float(next_n) - 0.50
        elif isinstance(fallback_base, (int, float)):
            s_key = float(fallback_base) + 0.50
        else:
            s_key = 9998.50

        if debug:
            return s_key, prev_n, next_n
        return s_key

    def sanitize_title(raw):
        """
        Limpia residuos tipo: '", fontsize=14, pad=20, color="#b3b3b3'
        u otros argumentos capturados por regex laxas y compacta espacios/saltos.
        """
        if not raw:
            return raw
        txt = str(raw)

        # Si viene algo como: "Título", fontsize=14, ...
        txt = re.sub(r'(["\'])\s*,.*$', r"\1", txt)

        # Quita comillas envolventes si quedaron
        if (txt.startswith('"') and txt.endswith('"')) or (
            txt.startswith("'") and txt.endswith("'")
        ):
            txt = txt[1:-1]

        # Normaliza unicode y elimina saltos raros; luego compacta cualquier whitespace
        txt = clean_text_rich(txt)
        txt = re.sub(r"\s+", " ", txt)

        return txt.strip()

    def build_metrics_block_html(raw_text):
        # Normaliza texto y fuerza que los bullets "•" se conviertan en saltos reales
        text = clean_text_rich(raw_text).strip()
        text = re.sub(r"\s*[•\u2022]\s*", "\n• ", text)

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return None, None

        # Si la 1ª línea ya parece lista de métricas (tiene bullet o ":") -> sin título
        first = lines[0]
        if first.startswith(("•", "-", "*")) or ":" in first:
            title = ""  # <<--- sin título
            body_lines = lines
        else:
            title = first
            body_lines = lines[1:]

        # Extrae pares clave:valor; también separa sub-segmentos dentro de una misma línea
        items = []
        for l in body_lines:
            segs = re.split(r"[•\u2022]\s*", l)  # divide por bullets embebidos
            for seg in segs:
                seg = seg.lstrip("-* ").strip()
                if ":" in seg:
                    items.append(seg)

        if not items:
            # sin pares -> deja el texto plano
            html = "<pre>" + clean_text_rich(raw_text) + "</pre>"
            return title, html

        # Construye la lista. Dejamos \n al final de cada <li> para un salto real.
        li_html = "".join(f"<li>{i}</li>\n" for i in items)
        # Si no hay título, no ponemos <h3>
        html = f"<ul>\n{li_html}</ul>"
        if title:
            html = f"<h3>{title}</h3>\n{html}"
        return title, html

    # --------------------------
    # Vaciar bloques de texto
    # --------------------------
    def flush_text():
        nonlocal current_metadata, accumulated_html, current_cell_number, locked_cell_number
        if current_metadata and current_metadata["type"] == "text" and accumulated_html:
            # Une el contenido acumulado y elimina anchor-links sin meter saltos extras
            html_block = "\n".join(accumulated_html).strip()
            html_block = ANCHOR_LINK_RE.sub("", html_block)

            # KPIs embebidos simples (opcional)
            kpis = extract_kpis_from_text(
                BeautifulSoup(html_block, "html.parser").get_text()
            )
            if kpis:
                for k in kpis:
                    k["cell_number"] = base_num()
                    k["sort_key"] = float(base_num()) + 0.55  # debajo de la celda
                    k["dom_seq"] = bump_seq()
                    results.append(k)

            # Determina la celda de inserción
            cell_num = (
                locked_cell_number
                if isinstance(locked_cell_number, int)
                else (
                    current_cell_number
                    if isinstance(current_cell_number, int)
                    else 8000
                )
            )

            # Agrega el bloque de texto final
            results.append(
                {
                    "type": "text",
                    "title": current_metadata.get("titles", ["Text"])[0],
                    "text": html_block,
                    "cell_number": cell_num,
                    "insert_below_cell": True,
                    "sort_key": float(cell_num) + 0.60,  # explícitamente debajo
                    "dom_seq": bump_seq(),
                }
            )

        # Reset de acumuladores/estado
        accumulated_html.clear()
        current_metadata = None
        locked_cell_number = None

    processed_outputs = set()

    # >>> Bucle principal por el DOM (no usamos soup.descendants) <<<
    for el in soup.find_all(True, recursive=True):
        # Actualiza el contexto de celda con memo
        if el.name in ("div", "p", "h1", "h2", "h3", "h4", "h5"):
            nearest_num = find_nearest_cell_number(el, _cache=nearest_cache)
            if nearest_num is not None:
                current_cell_number = nearest_num

        # Al cruzar wrappers de celda, vacía texto si hay
        if is_cell_wrapper(el):
            flush_text()
            continue

        # Comentarios "Mint it"
        if isinstance(el, Comment):
            ctext = el.strip()
            if re.search(r"end[-\s]?text", ctext, re.IGNORECASE):
                if current_metadata and current_metadata["type"] == "text":
                    flush_text()
            else:
                flush_text()
                metadata = parse_mint_comment(el)
                if metadata:
                    current_metadata = metadata
                    pending_metadata = metadata
                    locked_cell_number = (
                        find_nearest_cell_number(el, _cache=nearest_cache)
                        or current_cell_number
                    )
            continue

        # Prompts de entrada -> cortar acumulación
        if is_input_prompt(el):
            flush_text()
            continue

        # Código (posibles exportaciones a archivo)
        if el.name in ("div", "pre") and "jp-CodeMirrorEditor" in " ".join(
            el.get("class") or []
        ):
            if file_map:
                raw_code = clean_text_basic(el.get_text().strip())
                if raw_code:
                    matches = TO_EXPORT_RE.findall(raw_code)
                    if matches:
                        referenced = {
                            os.path.basename(fname.strip()) for _, fname in matches
                        }
                        for clean_name in referenced:
                            for uploaded_name in file_map:
                                base_uploaded = os.path.basename(uploaded_name).strip()
                                if (
                                    base_uploaded.lower() == clean_name.lower()
                                    and uploaded_name not in used_files
                                ):
                                    b = base_num()
                                    results.append(
                                        {
                                            "type": "table",
                                            "title": clean_metric_name(base_uploaded),
                                            "file_path": file_map[uploaded_name],
                                            "cell_number": b,
                                            "inserted_in_place": True,
                                            "sort_key": float(b) + 0.20,
                                            "dom_seq": bump_seq(),
                                        }
                                    )
                                    used_files.add(uploaded_name)
            continue

        # Salidas de celda (texto/plots embebidos como texto)
        if (
            is_text_output(el)
            and current_metadata is None
            and not el.find("table", class_="dataframe")
        ):
            classes = " ".join(el.get("class") or [])
            # canónico: el propio RenderedText o su ancestro RenderedText
            canonical = (
                el
                if "RenderedText" in classes
                else el.find_parent("div", class_="jp-RenderedText") or el
            )

            key = id(canonical)
            if key in processed_outputs:
                continue
            processed_outputs.add(key)

            raw_text = clean_text_basic(canonical.get_text().strip())

            # >>> descartamos ruido (df.info, summaries, tochos sin estructura)
            if is_noise_text_block(raw_text):
                current_metadata = None
                continue

            # 1) Siempre intenta armar un bloque de métricas legible
            title, html_block = build_metrics_block_html(raw_text)

            # 2) Luego extrae KPIs (dos pasadas: normal y fallback)
            possible_kpis = extract_kpis_from_text(raw_text)
            if not possible_kpis:
                possible_kpis = extract_print_block_kpis(raw_text)  # tu fallback

            b = base_num()

            def add_kpis(kpis):
                for k in kpis:
                    if not is_probably_junk(k["title"]) and not is_probably_junk(
                        k["value"]
                    ):
                        results.append(
                            {
                                "type": "kpi",
                                "title": k["title"],
                                "value": k["value"],
                                "cell_number": b,
                                "sort_key": float(b) + 0.15,
                                "dom_seq": bump_seq(),
                            }
                        )

            def add_text_block():
                if html_block and (
                    html_block.count("<li>") >= 2 or raw_text.count("\n") >= 2
                ):
                    artefact = {
                        "type": "text",
                        "text": html_block,
                        "cell_number": b,
                        "sort_key": float(b) + 0.50,
                        "dom_seq": bump_seq(),
                    }
                    t = (title or "").strip()
                    if t:  # solo setear si hay título
                        artefact["title"] = t
                    results.append(artefact)

            mode = (group_print_kpis_mode or "auto").lower()
            if mode == "kpis":
                if possible_kpis:
                    add_kpis(possible_kpis)
            elif mode == "text":
                add_text_block()
            elif mode == "both":
                add_text_block()
                if possible_kpis:
                    add_kpis(possible_kpis)
            else:  # auto
                # si hay varios KPI -> bloque; si hay uno -> KPI; si no hay -> bloque
                if possible_kpis and len(possible_kpis) == 1:
                    add_kpis(possible_kpis)
                else:
                    add_text_block()
                    if possible_kpis and len(possible_kpis) > 1:
                        add_kpis(possible_kpis)

            current_metadata = None
            continue

        # Markdown renderizado (fuera de "Mint it")
        if (
            el.name == "div"
            and "jp-RenderedMarkdown" in (el.get("class") or [])
            and current_metadata is None
        ):
            raw_html = el.decode_contents().strip()
            if not raw_html:
                continue

            tmp = BeautifulSoup(raw_html, "html.parser")
            tags = list(tmp.children)
            non_heading_found = any(
                getattr(t, "name", None) not in ["h1", "h2", "a", None] for t in tags
            )
            if not non_heading_found and len("".join(tmp.stripped_strings)) < 5:
                continue

            raw_text = clean_text_basic(tmp.get_text().strip())
            title_el = tmp.find(["h1", "h2", "h3", "strong", "p"])
            title_text = (
                clean_text_rich(title_el.get_text(strip=True)) if title_el else "Text"
            )
            html_cleaned = ANCHOR_LINK_RE.sub("", raw_html)

            cell_num = (
                find_nearest_cell_number(el, _cache=nearest_cache)
                or current_cell_number
                or 8000
            )
            s_key, prev_n, next_n = compute_markdown_sort_key(
                el, fallback_base=cell_num, debug=True
            )

            if s_key >= 9000:
                s_key = float(cell_num) + 0.50

            results.append(
                {
                    "type": "text",
                    "title": title_text,
                    "text": html_cleaned,
                    "cell_number": cell_num,
                    "sort_key": float(s_key),
                    "dom_seq": bump_seq(),
                }
            )

            log.debug(
                "[md sort] title=%r prev=%r next=%r cell_num=%r -> sort_key=%r",
                title_text,
                prev_n,
                next_n,
                cell_num,
                s_key,
            )

            # KPI único dentro del markdown (opcional, justo después del texto)
            possible_kpis = extract_kpis_from_text(raw_text)
            if (
                possible_kpis
                and len(possible_kpis) == 1
                and not is_probably_junk(possible_kpis[0]["value"])
            ):
                results.append(
                    {
                        **possible_kpis[0],
                        "cell_number": cell_num,
                        "sort_key": float(s_key) + 0.01,
                        "dom_seq": bump_seq(),
                    }
                )
                current_metadata = None
            continue

        # Bloque activo por "Mint it"
        if current_metadata and getattr(el, "name", None) in [
            "p",
            "pre",
            "div",
            "img",
            "h1",
            "h2",
            "h3",
            "ul",
            "ol",
        ]:
            mtype = current_metadata["type"]
            titles = current_metadata.get("titles", []) or []
            value_raw = (
                clean_text_rich(current_metadata.get("value", ""))
                if mtype == "text"
                else clean_text_basic(current_metadata.get("value", "")) or None
            )
            values = (
                [
                    clean_text_rich(v) if mtype == "text" else clean_text_basic(v)
                    for v in value_raw.split(";")
                ]
                if value_raw
                else []
            )

            if mtype == "text" and hasattr(el, "decode_contents"):
                if el.name == "div":
                    first_child = next(
                        (c for c in el.children if hasattr(c, "name")), None
                    )
                    if first_child and first_child.name in ["ul", "ol"]:
                        pass
                    else:
                        html = el.decode_contents().strip()
                        if html:
                            html = ANCHOR_LINK_RE.sub("<br/><br/>", html)
                            accumulated_html.append(html)

            elif getattr(el, "name", None) == "img":
                src = el.get("src", "")
                if src.startswith("data:image") and src not in used_imgs:
                    active_metadata = (
                        pending_metadata if pending_metadata else current_metadata
                    )
                    if active_metadata and active_metadata.get("type") == "chart":
                        tlist = active_metadata.get("titles", []) or []
                        raw_title = (
                            tlist.pop(0)
                            if tlist
                            else (find_plt_title_upwards_only(el) or "Chart")
                        )
                        title = sanitize_title(raw_title)[:MAX_TITLE_LEN]
                        b = (
                            locked_cell_number
                            if isinstance(locked_cell_number, int)
                            else (
                                current_cell_number
                                if isinstance(current_cell_number, int)
                                else 8000
                            )
                        )
                        results.append(
                            {
                                "type": "chart",
                                "title": title,
                                "image_base64": src,
                                "cell_number": b,
                                "sort_key": float(b) + 0.10,
                                "dom_seq": bump_seq(),
                            }
                        )
                        used_imgs.add(src)
                        active_metadata["titles"] = tlist
                        pending_metadata = None
                        current_metadata = None

            elif mtype == "kpi":
                b = (
                    locked_cell_number
                    if isinstance(locked_cell_number, int)
                    else (
                        current_cell_number
                        if isinstance(current_cell_number, int)
                        else 8000
                    )
                )
                if titles and values and len(titles) == len(values):
                    for t, v in zip(titles, values):
                        if not is_probably_junk(t) and not is_probably_junk(v):
                            results.append(
                                {
                                    "type": "kpi",
                                    "title": t,
                                    "value": v,
                                    "cell_number": b,
                                    "sort_key": float(b) + 0.55,
                                    "dom_seq": bump_seq(),
                                }
                            )
                    current_metadata = None
                elif value_raw and not is_probably_junk(value_raw):
                    results.append(
                        {
                            "type": "kpi",
                            "title": titles[0] if titles else "KPI",
                            "value": value_raw,
                            "cell_number": b,
                            "sort_key": float(b) + 0.55,
                            "dom_seq": bump_seq(),
                        }
                    )
                    current_metadata = None
                else:
                    if "value" in current_metadata and current_metadata["value"]:
                        extracted = clean_text_basic(el.get_text())
                        if extracted and not is_probably_junk(extracted):
                            results.append(
                                {
                                    "type": "kpi",
                                    "title": titles[0] if titles else "KPI",
                                    "value": extracted,
                                    "cell_number": b,
                                    "sort_key": float(b) + 0.55,
                                    "dom_seq": bump_seq(),
                                }
                            )
                    current_metadata = None

    # Vaciado final
    flush_text()

    # Imágenes sueltas (charts que no capturó el bloque Mint)
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src.startswith("data:image") and src not in used_imgs:
            raw_title = (find_plt_title_upwards_only(img) or "Untitled Chart")[
                :MAX_TITLE_LEN
            ]
            title = sanitize_title(raw_title)
            cell_num = find_cell_number_for_element(img)
            if not is_probably_junk(title):
                results.append(
                    {
                        "type": "chart",
                        "title": clean_text_rich(title),
                        "image_base64": src,
                        "cell_number": cell_num,
                        "sort_key": float(cell_num) + 0.10,
                        "dom_seq": bump_seq(),
                    }
                )
                used_imgs.add(src)

    # Tablas no insertadas "in place"
    if file_map:
        for fname, path in file_map.items():
            if fname not in used_files:
                base_uploaded = os.path.basename(fname)
                results.append(
                    {
                        "type": "table",
                        "title": clean_metric_name(base_uploaded),
                        "file_path": path,
                        "cell_number": 9998,
                        "inserted_in_place": False,
                        "sort_key": 9998.80,
                        "dom_seq": bump_seq(),
                    }
                )
                used_files.add(fname)

    # Normalizar & ordenar
    for r in results:
        if not isinstance(r.get("cell_number"), (int, float)):
            r["cell_number"] = 9999
        if "sort_key" not in r:
            r["sort_key"] = float(r["cell_number"])
        if "dom_seq" not in r:
            r["dom_seq"] = bump_seq()

    results.sort(key=lambda x: (x["sort_key"], x["dom_seq"]))

    # Insertar observaciones en el DOM (solo los marcados)
    try:
        for r in results:
            if (
                r.get("type") == "text"
                and r.get("insert_below_cell")
                and isinstance(r.get("cell_number"), (int, float))
            ):
                _insert_markdown_after_cell_number(
                    soup, int(r["cell_number"]), r["text"]
                )
    except Exception as e:
        log.exception("Error insertando observaciones en el DOM: %s", e)

    if return_modified_html:
        return results, exported_filenames_order, str(soup)
    else:
        return results, exported_filenames_order
