"""保留旧导入路径，并转调 myharness 中的统一文档分发器。"""

from __future__ import annotations

from pathlib import Path

from utils.document_models import Document


def parse_document(
    file_path: str | Path,
    *,
    document_id: str | None = None,
) -> Document:
    """解析一个受支持的文档，并返回对应的单个 Document 对象。"""
    from myharness.fileparser import parse_document as parse_with_fileparser

    return parse_with_fileparser(file_path, document_id=document_id)


__all__ = ["Document", "parse_document"]
