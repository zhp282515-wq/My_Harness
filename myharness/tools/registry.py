from myharness.tools.base import BaseTool
from utils.logger_tool import logger
from importlib import util
import sys
from pathlib import Path


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:

        if tool.name in self._tools:
            logger.warning(f"工具名 {tool.name} 重复，已覆盖旧工具")
        try:
            self._tools[tool.name] = tool
            logger.info(f"{tool.name} 注册成功")
        except Exception as e:
            logger.error(f"注册失败：{e}")

    def get_tool(self, name: str) -> BaseTool | None:

        if name not in self._tools:
            logger.error(f"工具 {name} 不存在")
            return None

        tool = self._tools[name]

        return tool

    def list_tools(self) -> dict[str, BaseTool]:
        return dict(self._tools)

    def load_from_directory(self, directory: Path) -> None:
        # 步骤 1：目录不存在就直接返回
        #   —— 工具目录是可选的，没有不是错误
        if not directory.is_dir():
            logger.warning(f"{directory} 不是一个有效的工具文件夹")
            return

        # 步骤 2：遍历目录下的 .py 文件
        #   sorted() 保证顺序稳定（不然每次启动加载顺序不同）
        for py_file in sorted(directory.glob("*.py")):
            # 步骤 2b：跳过下划线开头的（__init__.py、__pycache__）
            if py_file.name.startswith("_"):
                continue

            # 步骤 3：动态加载模块
            #   module_name 只是个内部标识，加点号是为了归类
            module_name = f"myharness_dynamic_tools.{py_file.stem}"
            spec = util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                continue                        # ← 防御，spec 可能为 None
            module = util.module_from_spec(spec)

            # 登记到 sys.modules，保证模块身份唯一
            # （不写不会崩，但重复加载会生成不同的类对象，isinstance 会失效）
            sys.modules[module_name] = module

            spec.loader.exec_module(module)     # ← 真正执行文件里的代码

            # 步骤 4：从模块里找出所有 BaseTool 子类
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (
                    isinstance(obj, type)              # 是类，不是函数/变量
                    and issubclass(obj, BaseTool)      # 是 BaseTool 的子类
                    and obj is not BaseTool            # 但不是 BaseTool 自己
                ):
                    # 步骤 5 + 6：实例化，失败就记日志跳过
                    try:
                        self.register(obj())
                    except Exception as e:
                        logger.error(f"[工具加载失败] {attr_name}: {type(e).__name__}: {e}")