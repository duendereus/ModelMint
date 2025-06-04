from bs4 import BeautifulSoup, Comment
import re
import unicodedata
import os


def clean_text(text):
    """
    Removes invisible/control characters and common HTML artifacts like ¶.
    """
    return (
        "".join(c for c in text if unicodedata.category(c)[0] != "C")
        .replace("¶", "")  # ← elimina el símbolo pilcrow
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
            metadata[key.strip().lower()] = clean_text(val.strip())
    return metadata


def find_next_header_text(start):
    for sibling in start.next_siblings:
        if getattr(sibling, "name", None) in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            return clean_text(sibling.get_text())
    return None


def find_plt_title_in_code(start):
    for sibling in start.next_siblings:
        if getattr(sibling, "name", None) == "pre":
            match = re.search(r'plt\.title\(["\'](.+?)["\']\)', sibling.get_text())
            if match:
                return clean_text(match.group(1))
    return None


def clean_metric_name(fname):
    name = os.path.splitext(os.path.basename(fname))[0]
    # Remove UUID prefix if present
    if re.match(r"^[a-f0-9]{32}_", name):
        name = "_".join(name.split("_")[1:])
    return name.replace("_", " ").title()


def parse_jupyter_html(content):
    soup = BeautifulSoup(content, "html.parser")
    results = []
    current_metadata = None

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
            title = clean_text(current_metadata.get("title", "")) or None
            value = clean_text(current_metadata.get("value", "")) or None

            if not title:
                if mtype == "chart":
                    title = (
                        find_plt_title_in_code(current_metadata["anchor"])
                        or find_next_header_text(current_metadata["anchor"])
                        or "Chart"
                    )
                else:
                    title = (
                        find_next_header_text(current_metadata["anchor"])
                        or mtype.title()
                    )
                title = clean_text(title)
                current_metadata["title"] = title

            if mtype == "kpi":
                if value:
                    results.append(
                        {"type": "kpi", "title": title, "value": clean_text(value)}
                    )
                    current_metadata = None
                else:
                    extracted = clean_text(el.get_text())
                    if extracted and re.search(r"\$?[\d,]+(\.\d+)?", extracted):
                        results.append(
                            {"type": "kpi", "title": title, "value": extracted}
                        )
                        current_metadata = None

            elif mtype == "chart" and el.name == "img":
                src = el.get("src", "")
                if src.startswith("data:image"):
                    results.append(
                        {"type": "chart", "title": title, "image_base64": src}
                    )
                    current_metadata = None

            elif mtype == "text":
                if value:
                    results.append(
                        {"type": "text", "title": title, "text": clean_text(value)}
                    )
                    current_metadata = None
                else:
                    text = clean_text(el.get_text())
                    if text and text != ",":
                        results.append({"type": "text", "title": title, "text": text})
                        current_metadata = None

    return results
