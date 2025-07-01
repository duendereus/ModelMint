import re
import unicodedata
from bs4 import Comment


def clean_text(text):
    return (
        "".join(c for c in text if unicodedata.category(c)[0] != "C")
        .replace("\u2029", "")
        .replace("\xa0", " ")
        .replace("¶", "")
        .strip()
    )


def extract_kpis(soup):
    results = []
    seen = set()

    for tag in soup.find_all(["p", "div", "h2", "h3", "span", "li"]):
        text = tag.get_text(strip=True)
        if not text or text in seen:
            continue
        seen.add(text)

        # ❌ Reglas para ignorar contenido basura
        if (
            re.match(r"In\s*\[\d+\]", text)  # Celda tipo In[4]
            or text.strip().lower().startswith("in [")
            or text.strip() in {"#", ".", ":", "-", "=", "2024", "2025"}
            or len(text.strip()) < 3
            or text.count(" ") < 1
            or re.match(r"^\d{4}$", text)  # años
        ):
            continue

        # ✅ Reglas para detectar KPI con separador
        if (
            any(sep in text for sep in [":", "—", "-"])
            and len(text) <= 100
            and not text.lower().startswith("plt.")
        ):
            parts = re.split(r"[:—\-]", text, maxsplit=1)
            if len(parts) == 2:
                name, value = map(clean_text, parts)
                if name and value:
                    results.append(
                        {"type": "kpi", "name": name[:255], "value": value[:500]}
                    )

    return results


def extract_charts(soup):
    results = []
    used_sources = set()

    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src or src in used_sources:
            continue

        if src.startswith("data:image"):
            title = find_title_near(img)
            results.append(
                {
                    "type": "chart",
                    "name": title or "Chart",
                    "value": None,
                    "value_base64": src,
                }
            )
            used_sources.add(src)
    return results


def find_title_near(el):
    """
    Busca un título hacia arriba en la jerarquía para asociar a una gráfica.
    """
    visited = set()
    node = el
    for _ in range(5):
        if not node or node in visited:
            break
        visited.add(node)
        text = node.get_text(strip=True)
        if (
            text
            and len(text) > 5
            and any(c.isalpha() for c in text)  # debe tener letras
        ):
            return clean_text(text)
        node = node.parent
    return None


def extract_text_blocks(soup):
    """
    Extrae bloques de texto delimitados por comentarios: <!-- Mint it: Text --> y <!-- End Text -->
    """
    results = []
    current_text = []
    current_title = "Text"
    collecting = False

    for el in soup.descendants:
        if isinstance(el, Comment):
            text = el.strip()
            if text.lower().startswith("mint it:"):
                match = re.match(r"Mint it:\s*text(?:\s*\|\s*title=(.+))?", text, re.I)
                if match:
                    current_title = clean_text(match.group(1) or "Text")
                    collecting = True
                    current_text = []
            elif re.search(r"end[-\s]?text", text, re.I):
                if collecting and current_text:
                    html = "\n".join(current_text).strip()
                    if len(html) > 30:
                        results.append(
                            {
                                "type": "text",
                                "name": current_title,
                                "value": html,
                            }
                        )
                    collecting = False
                    current_text = []

        elif collecting and hasattr(el, "decode_contents"):
            inner = el.decode_contents().strip()
            if inner:
                current_text.append(inner)

    return results
