from bs4 import BeautifulSoup, Comment
import re
import unicodedata
import os


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
    if re.fullmatch(r"\d{2}:\d{2}(\.\d+)?", text):  # 14:11 or 14:11.356
        return True
    if re.fullmatch(r"\d{2}:\d{2}:\d{2}(\.\d+)?", text):
        return True
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2}(\.\d+)?)?)?", text):
        return True
    return False


def find_plt_title_upwards_only(el):
    def extract_title(text):
        patterns = [
            r'plt\.title\(\s*["\'](.*?)["\']\s*\)',
            r'ax\.set_title\(\s*["\'](.*?)["\']\s*[,)]',
            r'fig\.suptitle\(\s*["\'](.*?)["\']\s*[,)]',
            r"title\s*=\s*\{[\"']center[\"']:\s*[\"'](.*?)[\"']\}",  # NEW: df.plot(title=...)
        ]
        titles = []
        for pattern in patterns:
            try:
                matches = re.findall(pattern, text)
                if matches:
                    print(f"[DEBUG title match] Pattern: {pattern} -> {matches}")
                titles.extend([clean_text_rich(m) for m in matches])
            except re.error as e:
                print(f"[DEBUG regex error] Pattern: {pattern} -> {str(e)}")
        return titles

    visited = set()
    node = el
    for depth in range(10):
        if not node or node in visited:
            break
        visited.add(node)

        if hasattr(node, "get_text"):
            snippet = node.get_text()[:200].replace("\n", " ").strip()
            print(f"[DEBUG walk_up] Depth: {depth}, Text: {snippet}")
            found = extract_title(node.get_text())
            if found:
                for t in found:
                    if (
                        t.lower().startswith("top")
                        or t.lower().startswith("ticket")
                        or "migrar" in t.lower()
                        or "studio access" in t.lower()
                    ):
                        print(f"[DEBUG title found (relevant)] {t}")
                        return t
                print(f"[DEBUG title found (fallback)] {found[0]}")
                return found[0]

        if hasattr(node, "find_previous"):
            heading = node.find_previous(["h1", "h2", "h3", "strong"])
            if heading and heading.get_text(strip=True):
                htext = clean_text_rich(heading.get_text(strip=True))
                print(f"[DEBUG heading fallback] Found heading: {htext}")
                return htext

        node = node.parent

    print("[DEBUG title fallback] No title found upwards or from Axes")
    return None


def clean_metric_name(fname):
    name = os.path.splitext(os.path.basename(fname))[0]
    if re.match(r"^[a-f0-9]{32}_", name):
        name = "_".join(name.split("_")[1:])
    return name.replace("_", " ").title()


def is_input_prompt(el):
    return (
        el.name == "div"
        and "jp-InputPrompt" in el.get("class", [])
        and re.search(r"In\s*\[\d+\]", el.get_text())
    )


def is_cell_wrapper(el):
    return el.name == "div" and any(
        cls.startswith("jp-Cell") for cls in el.get("class", [])
    )


def extract_kpis_from_text(text):
    kpis = []
    for line in text.splitlines():
        if ":" in line:
            title, value = line.split(":", 1)
            title, value = clean_text_basic(title), clean_text_basic(value)
            if (
                title
                and value
                and not is_probably_junk(title)
                and not is_probably_junk(value)
            ):
                kpis.append({"type": "kpi", "title": title, "value": value})
    return kpis


def parse_jupyter_html(content):
    soup = BeautifulSoup(content, "html.parser")
    results = []
    current_metadata = None
    used_imgs = set()
    accumulated_html = []

    def flush_text():
        nonlocal current_metadata, accumulated_html
        if current_metadata and current_metadata["type"] == "text" and accumulated_html:
            text_block = "\n".join(accumulated_html).strip()
            text_block = re.sub(r"\n{2,}", "\n", text_block)
            results.append(
                {
                    "type": "text",
                    "title": current_metadata.get("titles", ["Text"])[0],
                    "text": text_block,
                }
            )
        accumulated_html.clear()
        current_metadata = None

    for el in soup.descendants:
        if is_cell_wrapper(el):
            flush_text()

        elif isinstance(el, Comment):
            comment_text = el.strip()
            if re.search(r"end[-\s]?text", comment_text, re.IGNORECASE):
                if current_metadata and current_metadata["type"] == "text":
                    flush_text()
            else:
                flush_text()
                metadata = parse_mint_comment(el)
                if metadata:
                    metadata["anchor"] = el
                    current_metadata = metadata

        elif is_input_prompt(el):
            flush_text()

        elif el.name in ["pre", "div"] and "output" in " ".join(el.get("class", [])):
            kpis = extract_kpis_from_text(el.get_text())
            if kpis:
                results.extend(kpis)
                current_metadata = None

        elif (
            current_metadata
            and hasattr(el, "name")
            and el.name in ["p", "pre", "div", "img", "h1", "h2", "h3", "ul", "ol"]
        ):
            mtype = current_metadata["type"]
            titles = current_metadata.get("titles", [])
            value_raw = (
                clean_text_rich(current_metadata.get("value", ""))
                if mtype == "text"
                else clean_text_basic(current_metadata.get("value", ""))
            ) or None
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
                        continue
                html = el.decode_contents().strip()
                html = re.sub(r"<a[^>]+anchor-link[^>]*>.*?</a>", "<br/><br/>", html)
                if html:
                    accumulated_html.append(html)

            elif mtype == "chart" and el.name == "img":
                title = (
                    titles.pop(0)
                    if titles
                    else (find_plt_title_upwards_only(el) or "Chart")
                )
                current_metadata["titles"] = titles
                src = el.get("src", "")
                if src.startswith("data:image") and src not in used_imgs:
                    results.append(
                        {
                            "type": "chart",
                            "title": clean_text_rich(title),
                            "image_base64": src,
                        }
                    )
                    used_imgs.add(src)
                    current_metadata = None

            elif mtype == "kpi":
                if titles and values and len(titles) == len(values):
                    for t, v in zip(titles, values):
                        if not is_probably_junk(t) and not is_probably_junk(v):
                            results.append({"type": "kpi", "title": t, "value": v})
                    current_metadata = None
                elif value_raw and not is_probably_junk(value_raw):
                    title = titles[0] if titles else "KPI"
                    results.append({"type": "kpi", "title": title, "value": value_raw})
                    current_metadata = None
                else:
                    extracted = clean_text_basic(el.get_text())
                    if extracted and not is_probably_junk(extracted):
                        title = titles[0] if titles else "KPI"
                        results.append(
                            {"type": "kpi", "title": title, "value": extracted}
                        )
                        current_metadata = None

    flush_text()

    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src.startswith("data:image") and src not in used_imgs:
            title = find_plt_title_upwards_only(img) or "Untitled Chart"
            if not is_probably_junk(title):
                results.append(
                    {
                        "type": "chart",
                        "title": clean_text_rich(title),
                        "image_base64": src,
                    }
                )
                used_imgs.add(src)

    return results
