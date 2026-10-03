"""小型 HTML 辅助函数。"""

from pathlib import Path


def local_file_uri(path: str | Path) -> str:
    """将本地文件路径转换为浏览器可识别的 file URI。"""
    return Path(path).expanduser().resolve().as_uri()


__all__ = ["local_file_uri"]
