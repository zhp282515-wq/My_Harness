"""Split parsed documents into retrieval-friendly chunks."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape, unescape
import re
from typing import Callable, Mapping, Sequence

from utils.document_models import (
    DOCXDocument,
    Document,
    MarkdownDocument,
    PDFDocument,
    TXTDocument,
    XLSXDocument,
)


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """A document fragment and metadata useful for indexing and citations."""

    content: str
    metadata: dict[str, object]


class DocumentSpliter:
    """Split supported parsed documents while retaining their source structure."""

    def __init__(
        self,
        chunk_size: int = 500,
        overlap: int = 100,
        separators: list[str] | None = None,
        length_function: Callable[[str], int] = len,
    ) -> None:
        if type(chunk_size) is not int or chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0")
        if type(overlap) is not int or overlap < 0:
            raise ValueError("overlap 不能小于 0")
        if overlap >= chunk_size:
            raise ValueError("overlap 必须小于 chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.separators = (
            separators
            if separators is not None
            else [
                "\n\n", "\n", "。", "！", "？", "!", "?", "；", ";", "…", ".", "，", ",", " "
            ]
        )
        self.length_function = length_function

    def split(
        self,
        document: Document,
        *,
        xlsx_header_rows: Mapping[str, int | Sequence[int]] | None = None,
    ) -> list[DocumentChunk]:
        """Split a parser result; XLSX header rows are one-based worksheet rows."""
        if isinstance(document, TXTDocument):
            base = self._base_metadata(document, "txt")
            chunks = self._pack_units(
                [document.text],
                base,
                {},
                preferred_separators=("。", "！", "？", "!", "?", "；", ";", "…", "."),
            )
        elif isinstance(document, MarkdownDocument):
            chunks = self._split_markdown(document)
        elif isinstance(document, XLSXDocument):
            chunks = self._split_xlsx(document, xlsx_header_rows or {})
        elif isinstance(document, DOCXDocument):
            chunks = self._split_pages(document, document.pages, "docx")
        elif isinstance(document, PDFDocument):
            chunks = self._split_pages(document, document.pages, "pdf")
        else:
            raise TypeError(f"不支持的文档类型：{type(document).__name__}")

        for index, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = index
        return chunks

    @staticmethod
    def _base_metadata(document: Document, file_format: str) -> dict[str, object]:
        return {"source_file": document.source_file, "file_format": file_format}

    def _pack_units(
        self,
        units: list[str],
        base_metadata: dict[str, object],
        extra_metadata: dict[str, object],
        *,
        preferred_separators: Sequence[str] | None = None,
    ) -> list[DocumentChunk]:
        """Pack contiguous source text into bounded chunks with exact character overlap."""
        text = "".join(units)
        if not text.strip():
            return []
        chunks: list[DocumentChunk] = []
        start = 0
        while start < len(text):
            end = start
            while end < len(text) and self.length_function(text[start : end + 1]) <= self.chunk_size:
                end += 1
            if end == start:
                end += 1
            if end < len(text):
                end = self._preferred_boundary(text, start, end, preferred_separators)
            content = text[start:end]
            if content.strip():
                chunks.append(
                    DocumentChunk(
                        content=content,
                        metadata={**base_metadata, **extra_metadata},
                    )
                )
            if end >= len(text):
                break
            next_start = self._overlap_start(text, end)
            start = max(start + 1, next_start)
        return chunks

    def _preferred_boundary(
        self,
        text: str,
        start: int,
        max_end: int,
        separators: Sequence[str] | None,
    ) -> int:
        floor = max(start + 1, max_end - max(1, self.chunk_size // 2))
        for choices in (list(separators or ()), list(self.separators)):
            candidates: list[int] = []
            for separator in choices:
                if not separator:
                    continue
                position = text.rfind(separator, floor, max_end)
                while position >= floor:
                    if separator == "." and self._period_is_not_sentence_end(text, start, position):
                        position = text.rfind(separator, floor, position)
                        continue
                    candidates.append(position + len(separator))
                    break
            if candidates:
                return max(candidates)
        return max_end

    @staticmethod
    def _period_is_not_sentence_end(text: str, start: int, position: int) -> bool:
        if position > 0 and position + 1 < len(text) and text[position - 1].isdigit() and text[position + 1].isdigit():
            return True
        token = re.search(r"([A-Za-z](?:[A-Za-z.]*)?)$", text[start:position])
        return bool(
            token
            and token.group(1).casefold()
            in {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e"}
        )

    def _overlap_start(self, text: str, end: int) -> int:
        if self.overlap == 0:
            return end
        start = end
        lower_bound = max(0, end - self.chunk_size + 1)
        while start > lower_bound and self.length_function(text[start - 1 : end]) <= self.overlap:
            start -= 1
        return start

    def _split_markdown(self, document: MarkdownDocument) -> list[DocumentChunk]:
        base = self._base_metadata(document, "markdown")
        lines = document.text.splitlines(keepends=True)
        heading_stack: list[tuple[int, str]] = []
        sections: list[tuple[tuple[tuple[int, str], ...], list[str]]] = []
        active: list[str] = []
        fence: str | None = None

        def flush() -> None:
            nonlocal active
            if active and "".join(active).strip():
                sections.append((tuple(heading_stack), active))
            active = []

        for line in lines:
            fence_match = re.match(r"^\s*(`{3,}|~{3,})", line)
            if fence is not None:
                active.append(line)
                if fence_match and fence_match.group(1)[0] == fence[0] and len(fence_match.group(1)) >= len(fence):
                    fence = None
                continue
            if fence_match:
                fence = fence_match.group(1)
                active.append(line)
                continue

            atx = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*(?:\r?\n)?$", line)
            setext = re.match(r"^\s{0,3}(=+|-+)\s*(?:\r?\n)?$", line)
            if atx:
                flush()
                level = len(atx.group(1))
                title = atx.group(2).strip()
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, title))
                continue
            if setext and active:
                level = 1 if setext.group(1).startswith("=") else 2
                title = active.pop().strip()
                while active and not active[-1].strip():
                    active.pop()
                flush()
                if title:
                    while heading_stack and heading_stack[-1][0] >= level:
                        heading_stack.pop()
                    heading_stack.append((level, title))
                continue
            active.append(line)
        flush()

        chunks: list[DocumentChunk] = []
        for path, section_lines in sections:
            section_text = "".join(section_lines)
            metadata = {
                **base,
                "heading_path": [title for _, title in path],
                "heading_level": path[-1][0] if path else None,
            }
            chunks.extend(self._pack_units([section_text], metadata, {}))
        return chunks

    def _split_xlsx(
        self,
        document: XLSXDocument,
        configured_headers: Mapping[str, int | Sequence[int]],
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for sheet in document.sheets:
            rows, source_start_row, raw_rows, merged_columns = self._parse_html_table(sheet.html)
            if not rows:
                continue
            requested = configured_headers.get(sheet.name)
            if requested is not None:
                header_rows = self._validate_header_rows(
                    requested,
                    len(rows),
                    sheet.name,
                    source_start_row=source_start_row,
                )
            else:
                header_rows = self._detect_header_rows(rows, sheet.name, merged_columns)
            first_header = header_rows[0]
            title_rows = [
                index
                for index, row in enumerate(rows[:first_header])
                if any(cell.strip() for cell in row)
            ]
            excluded_rows = set(title_rows) | set(header_rows)
            last_data_index = max(
                (
                    index
                    for index, row in enumerate(rows)
                    if index not in excluded_rows and any(cell.strip() for cell in row)
                ),
                default=header_rows[-1],
            )
            data_rows = [
                (index, rows[index])
                for index in range(header_rows[-1] + 1, last_data_index + 1)
            ]
            groups = [data_rows] if len(data_rows) <= 20 else [data_rows[i : i + 20] for i in range(0, len(data_rows), 20)]
            for group in groups:
                selected_indexes = title_rows + header_rows + [index for index, _ in group]
                content = self._rows_to_html(
                    [raw_rows[index] for index in selected_indexes],
                    sheet.name,
                    title_row_count=len(title_rows),
                    header_row_count=len(header_rows),
                )
                start_row = group[0][0] + 1 if group else None
                end_row = group[-1][0] + 1 if group else None
                metadata = {
                    **self._base_metadata(document, "xlsx"),
                    "sheet_name": sheet.name,
                    "title_rows": [index + source_start_row for index in title_rows],
                    "header_rows": [index + source_start_row for index in header_rows],
                    "data_row_start": start_row + source_start_row - 1 if start_row is not None else None,
                    "data_row_end": end_row + source_start_row - 1 if end_row is not None else None,
                    "data_row_count": len(group),
                    "cell_range": sheet.cell_range,
                }
                chunks.append(DocumentChunk(content=content, metadata=metadata))
        return chunks

    @staticmethod
    def _parse_html_table(html: str) -> tuple[list[list[str]], int, list[str], list[set[int]]]:
        rows: list[dict[int, str]] = []
        raw_rows: list[str] = []
        source_rows: list[int] = []
        merged_columns: list[set[int]] = []
        cell_pattern = re.compile(
            r"<(?:td|th)\b([^>]*)>(.*?)</(?:td|th)\s*>",
            flags=re.IGNORECASE | re.DOTALL,
        )
        for row_match in re.finditer(r"<tr\b[^>]*>(.*?)</tr\s*>", html, flags=re.IGNORECASE | re.DOTALL):
            raw_rows.append(row_match.group(0))
            cells = list(cell_pattern.finditer(row_match.group(1)))
            positioned: dict[int, str] = {}
            merged: set[int] = set()
            cursor = 0
            for cell in cells:
                ref = re.search(r"\bdata-cell\s*=\s*['\"]([A-Z]+)(\d+)['\"]", cell.group(1), re.IGNORECASE)
                column = cursor
                if ref:
                    column = 0
                    for char in ref.group(1).upper():
                        column = column * 26 + ord(char) - ord("A") + 1
                    column -= 1
                value = unescape(re.sub(r"<[^>]+>", " ", cell.group(2))).replace("\xa0", " ").strip()
                positioned[column] = value
                colspan_match = re.search(r"\bcolspan\s*=\s*['\"]?(\d+)", cell.group(1), re.IGNORECASE)
                colspan = int(colspan_match.group(1)) if colspan_match else 1
                if colspan > 1:
                    merged.update(range(column, column + colspan))
                cursor = column + colspan
            row_ref = re.search(r"\bdata-cell\s*=\s*['\"](?:[A-Z]+)(\d+)['\"]", row_match.group(1), re.IGNORECASE)
            source_rows.append(int(row_ref.group(1)) if row_ref else len(source_rows) + 1)
            rows.append(positioned)
            merged_columns.append(merged)
        width = max((max(row, default=-1) for row in rows), default=-1) + 1
        return (
            [[row.get(column, "") for column in range(width)] for row in rows],
            min(source_rows, default=1),
            raw_rows,
            merged_columns,
        )

    @staticmethod
    def _validate_header_rows(
        value: int | Sequence[int],
        row_count: int,
        sheet_name: str,
        *,
        source_start_row: int = 1,
    ) -> list[int]:
        values = [value] if isinstance(value, int) else list(value)
        if not values or any(
            type(index) is not int
            or index < source_start_row
            or index >= source_start_row + row_count
            for index in values
        ):
            raise ValueError(f"工作表 {sheet_name!r} 的表头行配置无效；请提供有效的 1-based 行号")
        values = sorted(set(values))
        if values != list(range(values[0], values[-1] + 1)):
            raise ValueError(f"工作表 {sheet_name!r} 的多行表头必须是连续行；请提供连续行号")
        return [index - source_start_row for index in values]

    def _detect_header_rows(
        self,
        rows: list[list[str]],
        sheet_name: str,
        merged_columns: list[set[int]] | None = None,
    ) -> list[int]:
        nonempty = [index for index, row in enumerate(rows) if any(cell.strip() for cell in row)]
        candidates: list[tuple[float, int]] = []
        for index in nonempty[:12]:
            current = rows[index]
            width = max(len(current), 1)
            filled = [cell.strip() for cell in current]
            populated = sum(bool(cell) for cell in filled)
            if populated < 2:
                continue
            following = next((rows[next_index] for next_index in nonempty if next_index > index), [])
            if not following:
                continue
            current_fill = populated / width
            next_fill = sum(bool(cell.strip()) for cell in following) / max(len(following), 1)
            textual = sum(bool(cell) and not self._looks_like_value(cell) for cell in filled) / populated
            unique = len({cell.casefold() for cell in filled if cell}) / populated
            width_match = min(len(current), len(following)) / max(len(current), len(following), 1)
            # Real data rows often mix labels and values; headers tend to contain
            # descriptive text in every populated column.
            score = (
                0.2 * current_fill
                + 0.45 * textual
                + 0.15 * unique
                + 0.1 * width_match
                + 0.1 * min(next_fill, 1.0)
            )
            if len(current) == len(following) and textual > self._text_ratio(following):
                score += 0.08
            # A title row is usually merged/sparse and has only one populated cell.
            if populated == 1:
                score -= 0.35
            candidates.append((score, index))

        if not candidates:
            last_index = nonempty[-1] if nonempty else -1
            if last_index >= 0:
                last_row = rows[last_index]
                populated = sum(bool(cell.strip()) for cell in last_row)
                if populated >= 2 and self._text_ratio(last_row) >= 0.75:
                    candidates.append((0.7, last_index))
        if not candidates:
            raise ValueError(
                f"无法可靠识别工作表 {sheet_name!r} 的表头；请通过 split(..., xlsx_header_rows={{'{sheet_name}': 行号}}) 指定 1-based 表头行"
            )
        candidates.sort(reverse=True)
        best_score, best_index = candidates[0]
        ambiguous = (
            len(candidates) > 1
            and candidates[1][1] != best_index + 1
            and best_score - candidates[1][0] < 0.08
        )
        if best_score < 0.62 or ambiguous:
            raise ValueError(
                f"无法可靠识别工作表 {sheet_name!r} 的表头（候选不明确）；请通过 split(..., xlsx_header_rows={{'{sheet_name}': 行号或连续行号列表}}) 指定"
            )

        # Join adjacent header-like rows where the upper row supplies grouped labels.
        header_rows = [best_index]
        for index in range(best_index - 1, -1, -1):
            if not any(cell.strip() for cell in rows[index]):
                break
            populated = sum(bool(cell.strip()) for cell in rows[index])
            if 1 < populated <= max(1, len(rows[index]) // 2) or (
                populated > 1
                and self._text_ratio(rows[index]) >= 0.8
                and self._row_looks_headerish(rows[index], rows[best_index])
            ) or (
                populated > 1
                and merged_columns is not None
                and bool(merged_columns[index])
            ):
                header_rows.insert(0, index)
            else:
                break
        return header_rows

    @staticmethod
    def _looks_like_value(value: str) -> bool:
        return bool(re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?%?", value.strip()))

    def _text_ratio(self, row: list[str]) -> float:
        values = [cell.strip() for cell in row if cell.strip()]
        return sum(not self._looks_like_value(value) for value in values) / max(len(values), 1)

    def _row_looks_headerish(self, row: list[str], following: list[str]) -> bool:
        return self._text_ratio(row) >= 0.75 and (not following or self._text_ratio(following) < self._text_ratio(row))

    @staticmethod
    def _rows_to_html(
        rows: list[str],
        sheet_name: str,
        *,
        title_row_count: int,
        header_row_count: int,
    ) -> str:
        parts = ["<table>", f"<caption>{escape(sheet_name)}</caption>"]
        if title_row_count:
            parts.append("<tbody class=\"table-title\">")
            for row in rows[:title_row_count]:
                parts.append(row)
            parts.append("</tbody>")
        header_start = title_row_count
        header_end = header_start + header_row_count
        parts.append("<thead>")
        for row in rows[header_start:header_end]:
            row = re.sub(r"<td(?=[\s>])", "<th", row, flags=re.IGNORECASE)
            row = re.sub(r"</td\s*>", "</th>", row, flags=re.IGNORECASE)
            parts.append(row)
        parts.append("</thead><tbody>")
        for row in rows[header_end:]:
            parts.append(row)
        parts.extend(["</tbody></table>"])
        return "".join(parts)

    def _split_pages(self, document: Document, pages, file_format: str) -> list[DocumentChunk]:
        base = self._base_metadata(document, file_format)
        return [
            DocumentChunk(
                content=page.content,
                metadata={**base, "page_number": page.page_number},
            )
            for page in pages
            if page.content.strip()
        ]


__all__ = ["DocumentChunk", "DocumentSpliter"]
