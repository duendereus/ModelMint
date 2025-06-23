from bs4 import BeautifulSoup, Comment
import re
import unicodedata
import os


def clean_text_basic(text):
    return (
        "".join(c for c in text if unicodedata.category(c)[0] != "C")
        .replace("\u2029", "")
        .replace("\xa0", " ")
        .replace("¶", "")
        .strip()
    )


def clean_text_rich(text):
    cleaned = (
        "".join(c for c in text if unicodedata.category(c)[0] != "C")
        .replace("\u2029", "\n")
        .replace("\xa0", " ")
        .replace("¶", "\n")
        .strip()
    )
    if "¶" in text or "\u2029" in text:
        print(f"[DEBUG clean_text_rich] Original: {repr(text)}")
        print(f"[DEBUG clean_text_rich] Cleaned: {repr(cleaned)}")
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


def find_plt_title_upwards_only(el):
    def extract_title(text):
        patterns = [
            r'plt\.title\(\s*["\'](.+?)["\']\s*\)',
            r'ax\.set_title\(\s*["\'](.+?)["\']\s*[,)]',
            r'fig\.suptitle\(\s*["\'](.+?)["\']\s*[,)]',
        ]
        titles = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                print(f"[DEBUG title match] Pattern: {pattern} -> {matches}")
            titles.extend([clean_text_rich(m) for m in matches])
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
                print(f"[DEBUG title found] {found[0]}")
                return found[0]
        node = node.parent
    print("[DEBUG title fallback] No title found upwards")
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
        and re.search(r"In\s*\[\d+\]:", el.get_text())
    )


def is_cell_wrapper(el):
    return el.name == "div" and any(
        cls.startswith("jp-Cell") for cls in el.get("class", [])
    )


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
            print(
                f"[DEBUG flush_text] Title: {current_metadata.get('titles', ['Text'])[0]}"
            )
            print(f"[DEBUG flush_text] Text block starts with: {text_block[:100]!r}")
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
                    print(
                        "[DEBUG end-text] Found <!-- End Text --> marker. Flushing text."
                    )
                    flush_text()
            else:
                flush_text()
                metadata = parse_mint_comment(el)
                if metadata:
                    print(f"[DEBUG comment] Parsed metadata: {metadata}")
                    metadata["anchor"] = el
                    current_metadata = metadata

        elif is_input_prompt(el):
            flush_text()
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
                html = re.sub(
                    r"<a[^>]+anchor-link[^>]*>.*?</a>", "<br/><br/>", html
                )  # 🔥 Limpiar ¶ y anchors
                if "anchor-link" in html or "¶" in html:
                    print(f"[DEBUG anchor-clean] Raw HTML with anchor: {html[:120]!r}")
                if html:
                    accumulated_html.append(html)

            elif mtype == "chart" and el.name == "img":
                title = (
                    titles.pop(0)
                    if titles
                    else (
                        find_plt_title_upwards_only(current_metadata["anchor"])
                        or "Chart"
                    )
                )
                current_metadata["titles"] = titles
                src = el.get("src", "")
                if src.startswith("data:image") and src not in used_imgs:
                    print(f"[DEBUG chart] Using title: {title}")
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
                        results.append({"type": "kpi", "title": t, "value": v})
                    current_metadata = None
                elif value_raw:
                    title = titles[0] if titles else "KPI"
                    results.append({"type": "kpi", "title": title, "value": value_raw})
                    current_metadata = None
                else:
                    extracted = clean_text_basic(el.get_text())
                    if extracted and re.search(r"^[\d,\.\%$]+$", extracted):
                        title = titles[0] if titles else "KPI"
                        results.append(
                            {
                                "type": "kpi",
                                "title": title,
                                "value": extracted,
                            }
                        )
                        current_metadata = None

    flush_text()

    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src.startswith("data:image") and src not in used_imgs:
            title = find_plt_title_upwards_only(img) or "Untitled Chart"
            print(
                f"[DEBUG fallback chart] Found image without metadata, title: {title}"
            )
            results.append(
                {
                    "type": "chart",
                    "title": clean_text_rich(title),
                    "image_base64": src,
                }
            )
            used_imgs.add(src)

    return results
