from typing import Any

from myharness.tools.base import BaseTool
import ast
from utils.logger_tool import logger
import subprocess
from datetime import datetime
import httpx
from pathlib import Path
from utils.path_tool import get_project_path


class CalculatorTool(BaseTool):

    @property
    def name(self) -> str:
        # 工具名
        return "calculator"

    @property
    def description(self) -> str:
        # 工具描述
        return "进行数学的相关计算并返回计算结果"

    @property
    def parameters(self) -> dict[str, Any]:
        # 工具参数
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "要计算的数学表达式"
                }
            },
            "required": ["expression"]
        }

    def run(self, **kwargs) -> str:
        # 工具执行函数
        expression = kwargs.get("expression", "")
        if not expression:
            logger.error(f" [{self.name}] 错误: 未提供表达式")
            return f" [{self.name}] 错误: 未提供表达式"
        try:
            tree = ast.parse(expression, mode="eval")
            allowed_nodes = (
                ast.Expression,
                ast.BinOp,
                ast.UnaryOp,
                ast.Constant,
                ast.Add,
                ast.Sub,
                ast.Mult,
                ast.Div,
                ast.FloorDiv,
                ast.Mod,
                ast.Pow,
                ast.USub,
                ast.UAdd,
            )
            for node in ast.walk(tree):
                if not isinstance(node, allowed_nodes):
                    logger.error(f" [{self.name}] 错误: 表达式包含不允许的节点类型 '{type(node).__name__}'")
                    return f" [{self.name}] 错误: 表达式包含不允许的节点类型 '{type(node).__name__}'"
            result = eval(compile(tree, "<calc>", "eval"))
            logger.info(f"{self.name}:{expression} 已完成")
            return str(result)
        except Exception as e:
            logger.error(f" [{self.name}] 错误: 计算失败 — {e}")
            return f" [{self.name}] 错误: 计算失败 — {e}"

class FileReadTool(BaseTool):

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return "读取给定路径的文件内容。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要读取的文件的绝对路径。",
                }
            },
            "required": ["path"]
        }

    def run(self, **kwargs) -> str:
        path = kwargs.get("path", "")
        if not path:
            logger.error(f" [{self.name}] 错误: 未提供路径")
            return f" [{self.name}] 错误: 未提供路径"

        # 路径沙箱：resolve() 展开 .. 和符号链接后再判断，防止越界读取
        try:
            target = Path(path).resolve()
            root = Path(get_project_path()).resolve()
        except Exception as e:
            return f" [{self.name}] 错误: 路径无法解析 — {e}"

        if not target.is_relative_to(root):
            logger.warning(f" [{self.name}] 拒绝越界读取: {target}")
            return f" [{self.name}] 错误: 路径超出允许范围（仅限项目目录内）"

        try:
            with open(target, "r", encoding="utf-8") as f:
                lines = []
                for line in f:
                    if line.strip():
                        lines.append(line.rstrip("\n"))
                logger.info(f"{self.name}:{path} 已完成")
                return "\n".join(lines)
        except Exception as e:
            logger.error(f" [{self.name}] 错误: 读取文件失败 — {e}")
            return f" [{self.name}] 错误: 读取文件失败 — {e}"

DANGEROUS_PATTERNS = [
    "rm -rf", "rm -r", "rmdir /s", "del /f", "del /q",
    "format ", "shutdown", "taskkill", "reg delete",
    "mkfs", "dd if=", "> /dev/sda", ":(){:|:&};:",
]

class BashTool(BaseTool):
    @property
    def name(self) -> str:
        return "bash_tool"

    @property
    def description(self) -> str:
        return "执行一个 bash 命令并返回它的输出。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 bash 命令。",
                }
            },
            "required": ["command"]
        }


    def run(self, **kwargs) -> str:
        command = kwargs.get("command", "")
        if not command:
            logger.error(f" [{self.name}] 错误: 未提供命令")
            return f" [{self.name}] 错误: 未提供命令"

        lower = command.lower()
        for bad in DANGEROUS_PATTERNS:
            if bad in lower:
                logger.warning(f" [{self.name}] 拒绝执行（命中 '{bad}'）: {command}")
                return f" [{self.name}] 错误: 命令被安全策略拒绝"
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            out_bytes, err_bytes = process.communicate(timeout=30)
            stdout = out_bytes.decode("gbk", errors="replace")
            stderr = err_bytes.decode("gbk", errors="replace")
            output = stdout
            if stderr:
                output += f"\n[stderr]: {stderr}"
            if process.returncode != 0:
                output += f"\n[exit code]: {process.returncode}"
            logger.info(f"{self.name}:{command} 已完成")
            return output.strip() if output.strip() else "(no output)"
        except subprocess.TimeoutExpired:
            subprocess.run(
                f"taskkill /F /T /PID {process.pid}",
                shell=True,
                capture_output=True,
            )
            process.communicate()
            logger.error(f" [{self.name}] 错误: 命令在30秒后超时了")
            return f" [{self.name}] 错误: 命令在30秒后超时了"
        except Exception as e:
            logger.error(f" [{self.name}] 执行命令出错: {e}")
            return f" [{self.name}] 执行命令出错: {e}"

class DateTool(BaseTool):

    @property
    def name(self) -> str:
        return "date_tool"

    @property
    def description(self) -> str:
        return "查询当天的日期以及时间"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "输出的结果"
                }
            },
            "required": []
        }

    def run(self, **kwargs) -> str:
        time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"{self.name} 已完成")
        return f"{time}"

class LocationTool(BaseTool):

    @property
    def name(self) -> str:
        return "location_tool"

    @property
    def description(self) -> str:
        return "根据查询用户IP所在城市"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "输出用户的所在城市"
                }
            },
            "required": []
        }

    def run(self, **kwargs) -> str:
        try:
            resp = httpx.get("https://ipwho.is/", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    city_en = data["city"]

                    geo_resp = httpx.get(
                        "https://geocoding-api.open-meteo.com/v1/search",
                        params={"name": city_en, "count": 1, "language": "zh"},
                        timeout=10,
                    )
                    if geo_resp.status_code == 200:
                        geo_data = geo_resp.json()
                        if "results" in geo_data and geo_data["results"]:
                            return geo_data["results"][0]["name"]
        except Exception as e:
            logger.warning(f" [{self.name}]  IP定位失败：{e}")
        return f" [{self.name}] 未知城市"