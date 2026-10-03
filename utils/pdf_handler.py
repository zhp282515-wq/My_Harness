"""按页解析原生 PDF 和扫描 PDF，输出单页 HTML 内容。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
from html import escape
from pathlib import Path
import re
from uuid import uuid4

from utils.document_models import PDFDocument, PDFPage
from utils.html_utils import local_file_uri
from utils.logger_tool import logger


_MIN_NATIVE_TEXT_CHARS = 20
_HEADER_FOOTER_RATIO = 0.08
_HEADER_FOOTER_PAGE_RATIO = 0.5
_HEADER_FOOTER_MIN_PAGE_RATIO = 0.5
_SCAN_PAGE_PROMPT = """请完整读取这张 PDF 页面图片中的内容并输出紧凑、有效的 HTML 片段。
要求：按页面阅读顺序保留所有可读正文、标题、列表、公式说明和图文关系；表格必须转成 <table><tbody><tr><td>...</td></tr></tbody></table> 结构；遇到页面中的图片、图示或图表，请在对应位置写入简短准确的“图片描述：...”文本；不要重复同一内容，不要输出 Markdown 代码围栏，不要添加页面之外的说明。
忽略页眉、页脚、页码、扫描水印和装订边缘内容。"""


@dataclass(frozen=True, slots=True)
class _PageElement:
    y: float
    x: float
    html: str


def _page_text(page) -> str:
    return page.get_text("text", sort=True)


def _normalize_repeated_text(value: str) -> str:
    return re.sub(r"\s+", "", value).strip().casefold()


def _text_blocks(page) -> list[dict]:
    return [
        block
        for block in page.get_text("dict", sort=True).get("blocks", [])
        if block.get("type") == 0 and any(
            span.get("text", "").strip()
            for line in block.get("lines", [])
            for span in line.get("spans", [])
        )
    ]


def _find_repeated_marginalia(pages) -> set[str]:
    """只标记至少半数页面重复出现的页顶/页底文字块。"""
    if len(pages) < 2:
        return set()

    page_keys: list[set[str]] = []
    for page in pages:
        height = float(page.rect.height)
        keys: set[str] = set()
        for block in _text_blocks(page):
            _, y0, _, y1 = block["bbox"]
            if y1 <= height * _HEADER_FOOTER_RATIO or y0 >= height * (1 - _HEADER_FOOTER_RATIO):
                text = "".join(
                    span.get("text", "")
                    for line in block.get("lines", [])
                    for span in line.get("spans", [])
                )
                key = _normalize_repeated_text(text)
                if key:
                    keys.add(key)

        # PDF 有时把页码单独绘制在边缘；一位或多位纯数字作为重复边缘标记。
        for block in _text_blocks(page):
            _, y0, _, y1 = block["bbox"]
            if y1 <= height * _HEADER_FOOTER_RATIO or y0 >= height * (1 - _HEADER_FOOTER_RATIO):
                text = "".join(
                    span.get("text", "")
                    for line in block.get("lines", [])
                    for span in line.get("spans", [])
                ).strip()
                if re.fullmatch(r"[\d０-９]+", text):
                    keys.add("<page-number>")
        page_keys.append(keys)

    counts = Counter(key for keys in page_keys for key in keys)
    threshold = max(2, int(len(pages) * _HEADER_FOOTER_PAGE_RATIO + 0.999))
    return {
        key for key, count in counts.items()
        if count >= threshold and count / len(pages) >= _HEADER_FOOTER_MIN_PAGE_RATIO
    }


def _block_text(block: dict) -> str:
    lines: list[str] = []
    for line in block.get("lines", []):
        spans = line.get("spans", [])
        value = "".join(span.get("text", "") for span in spans)
        if value:
            lines.append(value)
    return re.sub(r"[\r\n]+", " ", " ".join(lines)).strip()


def _block_html(
    block: dict,
    excluded_rects: tuple[tuple[float, float, float, float], ...] = (),
) -> str:
    lines = [
        line
        for line in block.get("lines", [])
        if not any(
            _overlap_ratio(tuple(line.get("bbox", (0, 0, 0, 0))), rect) >= 0.5
            for rect in excluded_rects
        )
    ]
    text = re.sub(
        r"[\r\n]+",
        " ",
        " ".join("".join(span.get("text", "") for span in line.get("spans", [])) for line in lines),
    ).strip()
    if not text:
        return ""
    spans = [
        span
        for line in lines
        for span in line.get("spans", [])
    ]
    max_size = max((span.get("size", 0) for span in spans), default=0)
    bold = any(span.get("flags", 0) & 16 for span in spans)
    body = escape(text, quote=False)
    if bold:
        body = f"<strong>{body}</strong>"
    tag = "h2" if max_size >= 18 else "h3" if max_size >= 14 else "p"
    return f'<{tag} style="white-space: pre-wrap">{body}</{tag}>'


def _overlap_ratio(rect: tuple[float, float, float, float], outer: tuple[float, float, float, float]) -> float:
    overlap_width = max(0.0, min(rect[2], outer[2]) - max(rect[0], outer[0]))
    overlap_height = max(0.0, min(rect[3], outer[3]) - max(rect[1], outer[1]))
    rect_area = max(0.0, rect[2] - rect[0]) * max(0.0, rect[3] - rect[1])
    if rect_area == 0:
        return 0.0
    return overlap_width * overlap_height / rect_area


def _table_html(table, table_id: int, page=None) -> str:
    rows = table.extract()
    if not rows:
        return ""

    slot_count = sum(len(row) for row in rows)
    populated_count = sum(bool((value or "").strip()) for row in rows for value in row)
    density = populated_count / slot_count if slot_count else 0
    sparse_threshold = 0.35 if table.row_count >= 8 or table.col_count >= 6 else 0.2
    # PyMuPDF's line strategy can mistake text glyphs for borders and split one
    # visual cell into many pseudo-cells. Prefer strict ruling-line detection when
    # the resulting grid is sparse, provided it preserves the extracted text.
    if slot_count and density < sparse_threshold:
        strict_table = _strict_table_candidate(table, page)
        if strict_table is not None:
            strict_rows = strict_table.extract()
            if _table_text_coverage(table, rows, strict_table, strict_rows) >= 0.98:
                return _sparse_table_html(strict_table, table_id, strict_rows)
        return _sparse_table_html(table, table_id, rows)

    return _grid_table_html(table, table_id, rows)


def _table_text_coverage(reference_table, reference_rows: list[list[str]],
                         candidate_table, candidate_rows: list[list[str]]) -> float:
    """Compare text after removing detector duplicates caused by overlapping cells."""
    reference = Counter(_table_text_stream(reference_table, reference_rows))
    candidate = Counter(_table_text_stream(candidate_table, candidate_rows))
    total = max(sum(reference.values()), sum(candidate.values()))
    if not total:
        return 1.0

    # Table detectors can enumerate equivalent cells in different orders, so compare
    # character counts rather than flattened strings; geometry restores visual order.
    matched = sum(min(count, candidate[character]) for character, count in reference.items())
    return matched / total


def _table_text_stream(table, rows: list[list[str]]) -> str:
    candidates: list[tuple[tuple[float, float, float, float], str]] = []
    for table_row, values in zip(table.rows, rows):
        for column_index, value in enumerate(values):
            text = (value or "").strip()
            if not text or column_index >= len(table_row.cells):
                continue
            cell = table_row.cells[column_index]
            if cell is not None:
                candidates.append((tuple(float(coordinate) for coordinate in cell), text))

    # Long merged-cell text may be repeated as clipped fragments in smaller cells.
    kept: list[tuple[tuple[float, float, float, float], str]] = []
    for rect, text in sorted(
        candidates,
        key=lambda item: len(_compact_cell_text(item[1])),
        reverse=True,
    ):
        compact_text = _compact_cell_text(text)
        if any(
            compact_text in _compact_cell_text(other_text)
            and _overlap_ratio(rect, other_rect) >= 0.75
            for other_rect, other_text in kept
        ):
            continue
        kept.append((rect, text))
    return "".join(
        _compact_cell_text(text)
        for _, text in sorted(kept, key=lambda item: (round(item[0][1], 1), round(item[0][0], 1)))
    )


def _grid_table_html(table, table_id: int, rows: list[list[str]]) -> str:
    html = [
        f'<table data-table-id="pdf-table-{table_id}" '
        'style="border-collapse:collapse;width:100%;table-layout:auto"><tbody>'
    ]
    for row in rows:
        html.append("<tr>")
        for value in row:
            normalized = re.sub(r"[\r\n]+", " ", value or "").strip()
            html.append(
                f'<td style="border:1px solid #999;padding:4px;vertical-align:top;'
                f'white-space:pre-wrap">{escape(normalized, quote=False)}</td>'
            )
        html.append("</tr>")
    html.append("</tbody></table>")
    return "".join(html)


def _sparse_table_html(table, table_id: int, extracted_rows: list[list[str]]) -> str:
    """Serialize sparse/merged PDF tables without detector-created empty columns."""
    x_edges = {round(float(table.bbox[0]), 1), round(float(table.bbox[2]), 1)}
    candidates: list[tuple[int, int, tuple[float, float, float, float], str]] = []
    for row_index, (table_row, values) in enumerate(zip(table.rows, extracted_rows)):
        for column_index, value in enumerate(values):
            text = (value or "").strip()
            if not text or column_index >= len(table_row.cells):
                continue
            cell = table_row.cells[column_index]
            if cell is None:
                continue
            rect = tuple(float(coordinate) for coordinate in cell)
            if rect[2] - rect[0] >= 12:
                x_edges.update((round(rect[0], 1), round(rect[2], 1)))
            candidates.append((row_index, column_index, rect, text))

    if not candidates:
        return ""

    boundaries = _cluster_table_boundaries(x_edges)
    if len(boundaries) < 2:
        return ""

    # A merged cell can be returned once as its full text and again as fragments in
    # smaller overlapping cells. Keep the complete cell and discard those fragments.
    kept: list[tuple[int, int, tuple[float, float, float, float], str]] = []
    for candidate in sorted(
        candidates,
        key=lambda item: len(_compact_cell_text(item[3])),
        reverse=True,
    ):
        _, _, rect, text = candidate
        compact_text = _compact_cell_text(text)
        duplicated_by_larger_cell = any(
            compact_text in _compact_cell_text(other_text)
            and len(_compact_cell_text(other_text)) >= len(compact_text)
            and _overlap_ratio(rect, other_rect) >= 0.75
            for _, _, other_rect, other_text in kept
        )
        if not duplicated_by_larger_cell:
            kept.append(candidate)

    # Rebuild visual rows from cell Y coordinates instead of trusting detector
    # fragments. This joins wrapped paragraph lines but keeps vertically adjacent
    # fields and table rows separate.
    row_tops = _cluster_table_boundaries(
        {round(rect[1], 1) for _, _, rect, _ in kept}
    )
    cells_by_row: dict[
        int,
        list[tuple[int, int, tuple[float, float, float, float], str]],
    ] = {}
    for _, _, rect, text in kept:
        row_index = _nearest_table_boundary(row_tops, rect[1])
        start = _nearest_table_boundary(boundaries, rect[0])
        end = _nearest_table_boundary(boundaries, rect[2])
        if end <= start:
            end = min(start + 1, len(boundaries) - 1)
        cells_by_row.setdefault(row_index, []).append((start, end, rect, text))

    column_widths = [right - left for left, right in zip(boundaries, boundaries[1:])]
    total_width = sum(column_widths) or 1.0
    column_styles = "".join(
        f'<col style="width:{width / total_width * 100:.2f}%">'
        for width in column_widths
    )

    html = [
        f'<table data-table-id="pdf-table-{table_id}" '
        'style="border-collapse:collapse;width:100%;table-layout:fixed">'
        f"<colgroup>{column_styles}</colgroup><tbody>"
    ]
    for row_index in sorted(cells_by_row):
        cells = sorted(cells_by_row[row_index], key=lambda item: (item[0], item[1]))
        html.append("<tr>")
        cursor = 0
        for start, end, rect, text in cells:
            start = max(start, cursor)
            if end <= start:
                continue
            if start > cursor:
                html.append(_empty_table_cell(start - cursor))
            colspan = end - start
            attrs = f' colspan="{colspan}"' if colspan > 1 else ""
            if rect[2] - rect[0] <= 30 and rect[3] - rect[1] >= (rect[2] - rect[0]) * 2:
                pieces = [piece.strip() for piece in re.split(r"\s+", text) if piece.strip()]
                body = "<br>".join(escape(piece, quote=False) for piece in pieces)
            else:
                normalized = re.sub(r"\s+", " ", text).strip()
                body = escape(normalized, quote=False)
            html.append(
                f'<td{attrs} style="border:1px solid #999;padding:4px;'
                f'vertical-align:top;overflow-wrap:anywhere">{body}</td>'
            )
            cursor = end
        if cursor < len(column_widths):
            html.append(_empty_table_cell(len(column_widths) - cursor))
        html.append("</tr>")
    html.append("</tbody></table>")
    return "".join(html)


def _strict_table_candidate(table, page=None):
    """Retry table detection without text-derived edges that create pseudo-columns."""
    page = page or getattr(table, "page", None)
    if page is None:
        return None
    try:
        candidates = page.find_tables(strategy="lines_strict").tables
    except Exception:
        logger.exception("[PDF] 严格表格检测失败，继续使用坐标恢复")
        return None

    target = tuple(float(value) for value in table.bbox)
    best = None
    best_overlap = 0.0
    for candidate in candidates:
        overlap = _overlap_ratio(tuple(float(value) for value in candidate.bbox), target)
        if overlap > best_overlap:
            best, best_overlap = candidate, overlap
    return best if best_overlap >= 0.75 else None


def _cluster_table_boundaries(edges: set[float]) -> list[float]:
    """Collapse near-coincident cell edges without merging genuinely narrow columns."""
    ordered = sorted(edges)
    if len(ordered) < 2:
        return ordered

    # Opposite sides of a printed border often differ by about 5 points in
    # PyMuPDF. Six points collapses those duplicates while preserving any column
    # wide enough to hold readable text in a typical rendered document.
    tolerance = 6.0
    clusters: list[list[float]] = []
    for edge in ordered:
        if clusters and edge - clusters[-1][-1] <= tolerance:
            clusters[-1].append(edge)
        else:
            clusters.append([edge])
    return [sum(cluster) / len(cluster) for cluster in clusters]


def _nearest_table_boundary(boundaries: list[float], x: float) -> int:
    return min(range(len(boundaries)), key=lambda index: abs(boundaries[index] - x))


def _empty_table_cell(colspan: int) -> str:
    attrs = f' colspan="{colspan}"' if colspan > 1 else ""
    return f'<td{attrs} style="border:1px solid #999;padding:4px"></td>'


def _compact_cell_text(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _is_repeated_marginalia(block: dict, page, repeated_marginalia: set[str]) -> bool:
    _, y0, _, y1 = block["bbox"]
    height = float(page.rect.height)
    in_margin = (
        y1 <= height * _HEADER_FOOTER_RATIO
        or y0 >= height * (1 - _HEADER_FOOTER_RATIO)
    )
    if not in_margin:
        return False
    text = _block_text(block)
    key = _normalize_repeated_text(text)
    return key in repeated_marginalia or (
        "<page-number>" in repeated_marginalia
        and bool(re.fullmatch(r"[\d０-９]+", text.strip()))
    )


def _describe_image(image_path: Path) -> str:
    from utils.vlm import parse_image

    return parse_image(
        str(image_path),
        prompt="请用中文简洁准确地描述这张 PDF 页面中的图片或图示内容，不要描述整页文字。",
    ).replace("\r", " ").replace("\n", " ").strip()


def _render_image_block(
    block: dict,
    page,
    assets_dir: Path,
    sequence: int,
    image_cache: dict[str, tuple[Path, str]],
) -> tuple[str, int]:
    import pymupdf

    image_bytes = block.get("image")
    if image_bytes:
        digest = hashlib.sha256(image_bytes).hexdigest()
        extension = re.sub(r"[^a-zA-Z0-9]", "", block.get("ext", "png")).lower() or "png"
    else:
        pixmap = page.get_pixmap(
            clip=pymupdf.Rect(block["bbox"]),
            matrix=pymupdf.Matrix(2, 2),
            alpha=False,
        )
        image_bytes = pixmap.tobytes("png")
        digest = hashlib.sha256(image_bytes).hexdigest()
        extension = "png"

    cached = image_cache.get(digest)
    is_first_occurrence = cached is None
    if cached is None:
        output = assets_dir / f"image_{sequence:04d}.{extension}"
        output.write_bytes(image_bytes)
        try:
            description = _describe_image(output)
        except Exception:
            logger.exception("[PDF] 图片描述失败：%s", output)
            description = "[图片描述生成失败]"
        image_cache[digest] = (output, description)
        sequence += 1
    else:
        output, description = cached

    caption = (
        f"<figcaption>图片描述：{escape(description, quote=False)}</figcaption>"
        if is_first_occurrence
        else ""
    )
    html = (
        f'<figure><img src="{escape(local_file_uri(output), quote=True)}" alt="图片" '
        'style="max-width:100%;height:auto">'
        f"{caption}</figure>"
    )
    return html, sequence


def _native_page_html(page, repeated_marginalia: set[str], assets_dir: Path,
                      image_sequence: int,
                      image_cache: dict[str, tuple[Path, str]]) -> tuple[str, int]:
    page_dict = page.get_text("dict", sort=True)
    tables = page.find_tables().tables
    table_data: list[tuple[tuple[float, float, float, float], str]] = []
    for table_index, table in enumerate(tables, start=1):
        table_bbox = tuple(float(value) for value in table.bbox)
        table_html = _table_html(table, table_index, page)
        if table_html:
            table_data.append((table_bbox, table_html))

    elements: list[_PageElement] = []
    for block in page_dict.get("blocks", []):
        bbox = tuple(float(value) for value in block.get("bbox", (0, 0, 0, 0)))
        y0, x0 = bbox[1], bbox[0]
        if block.get("type") == 0:
            text = _block_text(block)
            if not text or _is_repeated_marginalia(block, page, repeated_marginalia):
                continue
            overlapping_tables = tuple(
                table_bbox
                for table_bbox, _ in table_data
                if _overlap_ratio(bbox, table_bbox) > 0
            )
            block_html = _block_html(block, overlapping_tables)
            if block_html:
                elements.append(_PageElement(y0, x0, block_html))
        elif block.get("type") == 1:
            html, image_sequence = _render_image_block(
                block, page, assets_dir, image_sequence, image_cache
            )
            elements.append(_PageElement(y0, x0, html))

    for bbox, html in table_data:
        elements.append(_PageElement(bbox[1], bbox[0], html))

    elements.sort(key=lambda element: (round(element.y, 1), round(element.x, 1)))
    return "".join(element.html for element in elements if element.html), image_sequence


def _scan_page_html(page, output_path: Path) -> str:
    import pymupdf
    from utils.vlm import parse_image

    page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).save(output_path)
    try:
        recognized = parse_image(str(output_path), prompt=_SCAN_PAGE_PROMPT)
        recognized = recognized.strip()
        if recognized.startswith("```"):
            recognized = re.sub(r"^```(?:html)?\s*|\s*```$", "", recognized, flags=re.IGNORECASE)
        if not recognized:
            raise ValueError("视觉模型未返回可用内容")
        recognized = re.sub(r"[\r\n]+", " ", recognized)
    except Exception:
        logger.exception("[PDF] 扫描页视觉解析失败：第 %d 页", page.number + 1)
        recognized = "<p>[本页视觉解析失败]</p>"
    image_html = (
        f'<figure><img src="{escape(local_file_uri(output_path), quote=True)}" '
        f'alt="PDF 第 {page.number + 1} 页扫描图" '
        'style="max-width:100%;height:auto"></figure>'
    )
    return f"{image_html}{recognized}"


def parse_pdf(file_path: str | Path, *, document_id: str | None = None) -> PDFDocument:
    """逐页解析 PDF；原生文字层使用 PyMuPDF，扫描页使用视觉模型。"""
    try:
        import pymupdf
    except ImportError as exc:
        raise ImportError("解析 PDF 需要 PyMuPDF：uv sync") from exc

    path = Path(file_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"PDF 文件不存在：{path}")
    doc_id = document_id or f"pending-{uuid4().hex}"
    if not re.fullmatch(r"[A-Za-z0-9._-]+", doc_id) or doc_id in {".", ".."}:
        raise ValueError("document_id 必须是单个路径片段，例如文档 MD5")

    assets_dir = Path(__file__).resolve().parent.parent / "data" / doc_id
    assets_dir.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(path) as pdf:
        repeated_marginalia = _find_repeated_marginalia(pdf)
        pages: list[PDFPage] = []
        image_sequence = 1
        image_cache: dict[str, tuple[Path, str]] = {}
        native_pages = scan_pages = 0
        for page in pdf:
            text_length = len(re.sub(r"\s+", "", _page_text(page)))
            if text_length >= _MIN_NATIVE_TEXT_CHARS:
                logger.debug("[PDF] 第 %d 页按原生文字层解析（字符数 %d）", page.number + 1, text_length)
                content, image_sequence = _native_page_html(
                    page, repeated_marginalia, assets_dir, image_sequence, image_cache
                )
                native_pages += 1
            else:
                output_path = assets_dir / f"page_{page.number + 1:04d}.png"
                # 空白页通常没有可识别内容，无需误报为扫描件，也避免不必要的 VLM 调用。
                if page.get_images(full=True) or page.get_drawings():
                    logger.info("[PDF] 第 %d 页按扫描页调用视觉模型（文字层字符数 %d）", page.number + 1, text_length)
                    content = _scan_page_html(page, output_path)
                    scan_pages += 1
                else:
                    logger.info("[PDF] 第 %d 页为空白页或无可解析内容", page.number + 1)
                    content = ""
            pages.append(PDFPage(page_number=page.number + 1, content=content))

    logger.info(
        "[PDF解析] 完成：%s，页数 %d，原生页 %d，扫描页 %d，资源目录 data/%s",
        path,
        len(pages),
        native_pages,
        scan_pages,
        doc_id,
    )
    return PDFDocument(source_file=str(path.resolve()), pages=tuple(pages))


__all__ = ["PDFDocument", "PDFPage", "parse_pdf", "render_pdf_pages"]


def render_pdf_pages(file_path: str | Path, output_dir: str | Path) -> tuple[Path, ...]:
    """按页将 PDF 渲染成 PNG，返回按页码排序的图片路径。"""
    try:
        import pymupdf
    except ImportError as exc:
        raise ImportError("PDF 页面渲染需要 PyMuPDF：uv add pymupdf") from exc

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF 文件不存在：{path}")

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    with pymupdf.open(path) as pdf:
        for index, page in enumerate(pdf, start=1):
            output = destination / f"page_{index:04d}.png"
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
            pixmap.save(output)
            rendered.append(output.resolve())
    return tuple(rendered)
