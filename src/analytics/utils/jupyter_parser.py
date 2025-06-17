from bs4 import BeautifulSoup, Comment
import re
import unicodedata
import os


def clean_text(text):
    return (
        "".join(c for c in text if unicodedata.category(c)[0] != "C")
        .replace("¶", "")
        .strip()
    )


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
            val = clean_text(val.strip())
            metadata[key] = val
            if key == "title":
                metadata["titles"] = [clean_text(t) for t in val.split(";")]
    return metadata


def find_next_header_text(start):
    for sibling in start.next_siblings:
        if getattr(sibling, "name", None) in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            return clean_text(sibling.get_text())
    return None


def find_plt_title_near_element(el):
    for sibling in el.next_siblings:
        if getattr(sibling, "name", None) in ["pre", "code"]:
            match = re.search(
                r'plt\.title\(\s*[\'"](.+?)[\'"]\s*\)', sibling.get_text()
            )
            if match:
                return clean_text(match.group(1))
    for sibling in el.previous_siblings:
        if getattr(sibling, "name", None) in ["pre", "code"]:
            match = re.search(
                r'plt\.title\(\s*[\'"](.+?)[\'"]\s*\)', sibling.get_text()
            )
            if match:
                return clean_text(match.group(1))
    return None


def clean_metric_name(fname):
    name = os.path.splitext(os.path.basename(fname))[0]
    if re.match(r"^[a-f0-9]{32}_", name):
        name = "_".join(name.split("_")[1:])
    return name.replace("_", " ").title()


def parse_jupyter_html(content):
    soup = BeautifulSoup(content, "html.parser")
    results = []
    current_metadata = None
    used_imgs = set()

    for el in soup.descendants:
        if isinstance(el, Comment):
            metadata = parse_mint_comment(el)
            if metadata:
                metadata["anchor"] = el
                current_metadata = metadata

        elif (
            current_metadata
            and hasattr(el, "name")
            and el.name in ["p", "pre", "div", "img", "h1", "h2", "h3"]
        ):
            mtype = current_metadata["type"]
            titles = current_metadata.get("titles", [])
            value_raw = clean_text(current_metadata.get("value", "")) or None
            values = [clean_text(v) for v in value_raw.split(";")] if value_raw else []

            # CHART ─────────────────────────────────────
            if mtype == "chart":
                title = (
                    titles.pop(0)
                    if titles
                    else (
                        find_plt_title_near_element(current_metadata["anchor"])
                        or find_next_header_text(current_metadata["anchor"])
                        or "Chart"
                    )
                )
                current_metadata["titles"] = titles

                if el.name == "img":
                    src = el.get("src", "")
                    if src.startswith("data:image") and src not in used_imgs:
                        results.append(
                            {
                                "type": "chart",
                                "title": clean_text(title),
                                "image_base64": src,
                            }
                        )
                        used_imgs.add(src)
                        if not titles:
                            current_metadata = None

            # KPI ─────────────────────────────────────
            elif mtype == "kpi":
                if titles and values and len(titles) == len(values):
                    for t, v in zip(titles, values):
                        results.append({"type": "kpi", "title": t, "value": v})
                    current_metadata = None
                elif value_raw:
                    title = (
                        titles[0]
                        if titles
                        else (
                            find_next_header_text(current_metadata["anchor"]) or "KPI"
                        )
                    )
                    results.append({"type": "kpi", "title": title, "value": value_raw})
                    current_metadata = None
                else:
                    extracted = clean_text(el.get_text())
                    if extracted and re.search(r"^[\d,\.%$]+$", extracted):
                        title = (
                            titles[0]
                            if titles
                            else (
                                find_next_header_text(current_metadata["anchor"])
                                or "KPI"
                            )
                        )
                        results.append(
                            {"type": "kpi", "title": title, "value": extracted}
                        )
                        current_metadata = None

            # TEXT ─────────────────────────────────────
            elif mtype == "text":
                title = (
                    titles[0]
                    if titles
                    else (find_next_header_text(current_metadata["anchor"]) or "Text")
                )
                text = clean_text(value_raw or el.get_text())
                if text and text != ",":
                    results.append({"type": "text", "title": title, "text": text})
                    current_metadata = None

    # 🖼️ Post-procesamiento: <img> sin comentario
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src.startswith("data:image") and src not in used_imgs:
            title = (
                find_plt_title_near_element(img)
                or find_next_header_text(img)
                or "Untitled Chart"
            )
            results.append(
                {"type": "chart", "title": clean_text(title), "image_base64": src}
            )
            used_imgs.add(src)

    return results
