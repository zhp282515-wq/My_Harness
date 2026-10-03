"""读取 Markdown 原文，不在解析阶段进行结构或 chunk 切分。"""

from pathlib import Path

from utils.document_models import MarkdownDocument


def _decode_file(raw: bytes, encoding: str | None) -> str:
    if encoding is not None:
        return raw.decode(encoding)
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("gb18030")


def parse_markdown(
    file_path: str | Path,
    *,
    encoding: str | None = None,
) -> MarkdownDocument:
    """读取 Markdown 全文并返回文档对象。

    不解析标题、表格或其他 Markdown 结构，原文内容完整保存在 ``text`` 中。
    默认先尝试 UTF-8（兼容 BOM），失败时回退到 GB18030；可通过 ``encoding`` 指定编码。
    """
    path = Path(file_path)
    content = _decode_file(path.read_bytes(), encoding)
    return MarkdownDocument(source_file=str(path.resolve()), text=content)


__all__ = ["MarkdownDocument", "parse_markdown"]
