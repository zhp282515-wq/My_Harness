"""按文件格式调用对应的解析器，并返回单个 Document 对象。"""

from pathlib import Path

from utils.document_models import Document
from utils.docx_handler import parse_docx
from utils.logger_tool import logger
from utils.markdown_handler import parse_markdown
from utils.pdf_handler import parse_pdf
from utils.txt_handler import parse_txt
from utils.xlsx_handler import parse_xlsx


_PARSERS = {
    ".txt": parse_txt,
    ".md": parse_markdown,
    ".markdown": parse_markdown,
    ".xlsx": parse_xlsx,
    ".docx": parse_docx,
    ".pdf": parse_pdf,
}


def parse_document(
    file_path: str | Path,
    *,
    document_id: str | None = None,
) -> Document:
    """解析一个受支持的文档。"""
    path = Path(file_path)
    if document_id is not None and path.suffix.lower() not in {".docx", ".pdf"}:
        raise ValueError("document_id 仅适用于 DOCX 和 PDF 文件")
    parser = _PARSERS.get(path.suffix.lower())
    if parser is None:
        supported = ", ".join(sorted(_PARSERS))
        logger.error(
            "[文档解析失败] 不支持的文件格式：%s（支持格式：%s）",
            path,
            supported,
        )
        raise ValueError(
            f"不支持的文档格式 {path.suffix!r}；支持格式：{supported}"
        )

    logger.info("[文档解析] 开始解析：%s", path)
    try:
        if path.suffix.lower() in {".docx", ".pdf"}:
            document = parser(path, document_id=document_id)
        else:
            document = parser(path)
    except Exception:
        logger.exception("[文档解析失败] 文件解析出错：%s", path)
        raise

    logger.info(
        "[文档解析] 解析完成：%s -> %s",
        path,
        type(document).__name__,
    )
    return document


__all__ = ["Document", "parse_document"]
