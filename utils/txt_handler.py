"""解析 TXT 文件并返回对应的文档对象。"""

from pathlib import Path

from utils.document_models import TXTDocument


def parse_txt(
    file_path: str | Path,
    *,
    encoding: str | None = None,
) -> TXTDocument:
    """读取 TXT 全文，不在解析阶段进行结构切分或 chunk 切分。

    默认先按 UTF-8（兼容 BOM）读取，解码失败后回退到 GB18030；也可指定编码。
    直接从字节解码，因此保留原文件中的空格、制表符和换行符。
    """
    path = Path(file_path)
    raw_content = path.read_bytes()

    if encoding is not None:
        content = raw_content.decode(encoding)
    else:
        try:
            content = raw_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = raw_content.decode("gb18030")

    return TXTDocument(source_file=str(path.resolve()), text=content)


__all__ = ["TXTDocument", "parse_txt"]
