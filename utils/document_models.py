"""文件解析器输出的最小文档数据模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TXTDocument:
    source_file: str
    text: str


@dataclass(frozen=True, slots=True)
class MarkdownDocument:
    source_file: str
    text: str


@dataclass(frozen=True, slots=True)
class XLSXSheet:
    name: str
    cell_range: str
    html: str


@dataclass(frozen=True, slots=True)
class XLSXDocument:
    source_file: str
    sheets: tuple[XLSXSheet, ...]


@dataclass(frozen=True, slots=True)
class DOCXPage:
    page_number: int
    content: str


@dataclass(frozen=True, slots=True)
class DOCXDocument:
    source_file: str
    pages: tuple[DOCXPage, ...]


@dataclass(frozen=True, slots=True)
class PDFPage:
    page_number: int
    content: str


@dataclass(frozen=True, slots=True)
class PDFDocument:
    source_file: str
    pages: tuple[PDFPage, ...]


Document = TXTDocument | MarkdownDocument | XLSXDocument | DOCXDocument | PDFDocument


__all__ = [
    "Document",
    "DOCXDocument",
    "DOCXPage",
    "MarkdownDocument",
    "PDFDocument",
    "PDFPage",
    "TXTDocument",
    "XLSXDocument",
    "XLSXSheet",
]
