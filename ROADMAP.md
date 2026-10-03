# My-Second-Harness 学习与实现规划

> **目标**：从 0 开始手敲一个完整的 Agent Harness，10 月 1 日（国庆节）之前全部完成并深刻理解。
> **开始日期**：2026-09-21　**截止日期**：2026-09-30　**总工期**：10 天
> **参考项目**：`C:\Users\Administrator\Desktop\Python-Project\FreeAutomation-Tech\agent-harness-main`

---

## 一、这个项目要做什么

一个**以文件系统为核心的 Agent 运行时**。核心思想：把一个 Agent 定义为磁盘上的一个目录。

```
my-agent/
├── agent.yml          # 模型、供应商、温度等配置
├── instructions.md    # 系统提示词（Agent 的"人格"）
├── skills/            # 技能文档（按需注入上下文）
└── tools/             # 该 Agent 专属的自定义工具（Python 文件）
```

运行时负责：加载目录 → 组装工具 → 调用大模型 → 执行工具 → 循环，直到任务完成。

---

## 二、学习纪律（重要）

**这个项目的代码由你自己一行一行敲。** 规划文档只给：

- 每一步的**目标**（做完之后应该能回答什么问题）
- **验收标准**（怎么知道自己做对了）
- **坑点提醒**（容易卡住的地方）

不给完整实现代码。卡住了可以问，但要先自己试。

**操作方式**：优先用 PyCharm 的可视化操作（右键 → Run、Run 菜单、Settings → Project → Python Interpreter、Terminal 面板），不要依赖命令行脚本。

---

## 三、全局目录规划

```
My-Second-Harness/
├── ROADMAP.md              # 本文件
├── pyproject.toml          # 依赖声明
├── .env                    # API Key（不提交 git）
├── myharness/              # 主包
│   ├── __init__.py
│   ├── loader.py           # ✅ 阶段 3：加载 agent 目录
│   ├── runtime.py          # ⬜ 阶段 4：ReAct 主循环（下一个）
│   ├── cli.py              # ⬜ 阶段 6：命令行入口
│   ├── tools/              # ✅ 阶段 1
│   │   ├── base.py         # BaseTool + to_schema()
│   │   ├── registry.py     # ToolRegistry + 动态加载
│   │   └── builtin.py      # calculator / file_read / bash_tool / date_tool
│   ├── providers/          # ✅ 阶段 2
│   │   ├── base.py         # ToolCall / ChatMessage / ChatResponse / BaseProvider
│   │   └── dashscope.py    # 通义千问实现（httpx 手搓 HTTP）
│   ├── agents/             # ✅ 阶段 3
│   │   └── base.py         # AgentDefinition（@dataclass）
│   ├── memory/             # ⬜ 阶段 5：对话记忆
│   │   └── store.py
│   └── server/             # ⬜ 阶段 7：FastAPI 服务
│       └── app.py
├── my_agent/               # ✅ 示例 Agent
│   ├── agent.yml           #   模型/temperature/tools 列表
│   ├── instructions.md     #   系统提示词（自动去掉空行）
│   ├── skills/partner.md   #   技能文档
│   └── tools/weather.py    #   自定义工具（真调 open-meteo API）
├── test_data/              # ✅ 5 个回归样本（txt / md / html）
├── utils/                  # ✅ 阶段 0
│   ├── logger_tool.py      #   控制台 + 按天文件双输出
│   └── path_tool.py        #   get_abs_path()
├── logs/                   # 按天切分的运行日志
│   └── harness_YYYY-MM-DD.log
└── tests/                  # ipynb 探索脚本（不用 pytest，见 1.4）
    ├── test_builtin.ipynb
    ├── test_registry.ipynb
    └── test_dashscope.py
```

---

## 四、十天日程总览

| 日期 | 阶段 | 交付物 | 状态 |
|------|------|--------|------|
| 09-21 | 阶段 0 + 阶段 1 | utils 两个工具 + tools 包跑通 | ✅ 已完成 |
| 09-22 | 阶段 2 + 阶段 3 | providers 包 + loader 包 | ✅ 已完成（提前 1 天） |
| 09-23 ~ 09-25 | 阶段 4 | runtime（ReAct 主循环） | ✅ 已完成 |
| 09-26 ~ 09-27 | 阶段 5 + 多会话 + 阶段 5.5 | memory/裁剪/技能按需加载 + session_id 隔离 + PG 持久化 + 输出截断续写 + Milvus 起容器 | ✅ 已完成 |
| 09-28 | RAG | Milvus 向量检索（先于 server，改动了原顺序） | 🔄 进行中 |
| 09-29 ~ 09-30 | 阶段 7 | server（FastAPI）+ 安全加固 | ⬜ |
| 待定 | 复盘 / 收尾 | 讲流程 + README | ⬜ |

> **阶段 6（CLI）已跳过** —— 见下文说明。
> **顺序调整（09-28）**：RAG 提到 server 之前做。原计划里 RAG 属于改装阶段第 3 步。
> **PostgreSQL 持久化**原计划在改装阶段，已于 09-27 提前完成。

**每日节奏建议**：20:00–23:00 三个小时，前 30 分钟复盘前一天代码，中间 2 小时新内容，最后 30 分钟写测试 + 记笔记。

---

## 阶段 0：环境准备（今晚，30 分钟）

### 目标
工程能跑起来，有日志、有路径工具，后面所有模块都用得上。

### 任务清单

**0.1 补齐依赖**

在 PyCharm 里打开 `My-Second-Harness`，进入 Terminal 面板执行：

```bash
uv add httpx pyyaml python-dotenv rich
uv add --dev pytest
```

**0.2 配置 API Key**

在项目根目录的 `.env` 里写入（用你自己的 key）：

```bash
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxx
```

**0.3 写 `utils/logger_tool.py`**

目标：全局唯一的 logger，输出带时间戳、文件名、行号。

- 用 `logging` 标准库
- 终端输出用 `rich.logging.RichHandler`（彩色、好看）
- 同时写一份到 `logs/harness.log`（用 `RotatingFileHandler`，单文件 5MB，保留 3 个备份）
- 暴露一个模块级变量 `logger`，其他模块 `from utils.logger_tool import logger` 直接用

**验收**：在 PyCharm 里右键这个文件 → Run，终端能看到带颜色的日志行，且 `logs/harness.log` 被创建。

**0.4 写 `utils/path_tool.py`**

目标：无论从哪里运行，都能拿到项目根目录的绝对路径。

- 提供 `get_project_root() -> Path`：从当前文件向上找，直到找到含 `pyproject.toml` 的目录
- 提供 `get_abs_path(relative: str) -> str`：拼接项目根 + 相对路径，返回字符串

**验收**：在 PyCharm 里 `print(get_abs_path("my_agent"))`，输出的是完整的 `C:\...\My-Second-Harness\my_agent`，不管你用哪个工作目录运行。

### 坑点提醒

- `RotatingFileHandler` 的 `logs/` 目录可能不存在，写之前先 `mkdir(exist_ok=True)`
- Windows 下路径分隔符是 `\`，用 `pathlib.Path` 而不是字符串拼接
- `RichHandler` 要配 `logging.Formatter("%(message)s")`，否则会重复打印时间

---

## 阶段 1：tools 包（今晚，2.5 小时）★ 今晚的核心目标

工具是 Agent 的"手"。这个包定义了三件事：**工具长什么样**（base）、**工具怎么被管理**（registry）、**自带哪些工具**（builtin）。

### 1.1 `tools/base.py` — 工具抽象基类

**目标**：回答"一个工具最少需要提供什么，大模型才能调用它？"

目前文件里已经有一个 `BaseTool` 骨架，**请先合上屏幕，自己想一遍**：大模型要知道什么，才敢调用一个工具？

答案是三样东西 —— 名字、描述、参数 schema，外加一个执行入口。

**任务**：
- 保留四个抽象成员：`name` / `description` / `parameters` / `run`
- 前三个用 `@property` + `@abstractmethod`，因为它们是"属性"而不是"方法"
- `run` 签名用 `**kwargs: Any`，**为什么不用固定参数？**（提示：参数是运行时从模型返回的 JSON 里解出来的，类型不固定）
- 返回类型统一是 `str` —— 为什么？（提示：工具结果最终要塞进对话消息里，消息内容必须是文本）
- 加一个 `to_schema() -> dict` 方法，把 name / description / parameters 打包成 OpenAI function-calling 格式：

```python
{
    "type": "function",
    "function": {
        "name": "...",
        "description": "...",
        "parameters": {...}
    }
}
```

**验证**：写一个最小的 `EchoTool` 子类，实例化后调用 `to_schema()`，打印出来看看格式对不对。

### 1.2 `tools/builtin.py` — 三个内置工具

**目标**：实现 Calculator / FileRead / Bash，并理解它们的**安全边界在哪**。

**1.2.1 CalculatorTool**

- 参数：`expression: str`
- 实现要点：**绝对不能用裸 `eval()`**。要先 `ast.parse(expression, mode="eval")`，然后 `ast.walk` 遍历所有节点，白名单校验：
  - 允许：`Expression, BinOp, UnaryOp, Constant, Add, Sub, Mult, Div, FloorDiv, Mod, Pow, USub, UAdd`
  - 只要出现不在白名单里的节点，直接返回错误字符串
- 思考题：为什么白名单比黑名单安全？（黑名单永远列不全，比如 `__import__` 的各种绕过）

**1.2.2 FileReadTool**

- 参数：`path: str`
- 实现要点：`open(path, "r", encoding="utf-8")`，异常捕获后返回 `f"Error reading file: {e}"`
- 思考题：现在这个实现能读 `C:\Windows\System32\...`，这安全吗？后面阶段 7 会讨论怎么加路径沙箱

**1.2.3 BashTool**

- 参数：`command: str`
- 实现要点：用 `Popen` + `communicate(timeout=30)`，**不是** `subprocess.run`
  - 原因：`run()` 超时时内部杀完就抛，拿不到 pid，无法清理孤儿进程
  - Windows 上超时后要 `taskkill /F /T /PID {pid}` 杀**整棵进程树**
  - 详见 **附录 A1**，这是实测踩出来的
- 必须保留 `shell=True`（否则 `dir` / `echo` 等 cmd 内置命令全部失效，见 **附录 A3**）
- 不用 `text=True`，拿 bytes 自己 `.decode("gbk", errors="replace")`（见 **附录 A2**）
- 必须单独捕获 `subprocess.TimeoutExpired`，且放在 `except Exception` **前面**（Python 从上到下匹配第一个命中的 except）

**统一约定（三个工具都要遵守）**：
- 出错时**返回错误字符串，不要抛异常**。原因：异常会中断 Agent 循环，而错误信息本身对模型是有用的反馈
- 每个工具的 `parameters` 必须是合法的 JSON Schema

**验收**：PyCharm 里右键 `builtin.py` → Run，逐个实例化三个工具，每个至少成功调用一次、失败调用一次（比如 `1/0`、读不存在的文件、跑 `sleep 60` 看超时）。观察返回值格式。

### 1.3 `tools/registry.py` — 工具注册表

**目标**：回答"Agent 怎么知道有哪些工具可用？以及用户丢进 `my_agent/tools/` 的 Python 文件怎么被自动发现？"

**任务**：

- 类名 `ToolRegistry`，内部维护 `dict[str, BaseTool]`
- 四个基础方法：
  - `register(tool)` — 以 `tool.name` 为 key 存进去（注意：同名会覆盖，想清楚这是不是你想要的行为）
  - `get(name) -> BaseTool | None`
  - `list_tools() -> dict` — **返回副本**，不要返回内部字典本身（为什么？防止外部误改内部状态）
  - `to_schemas() -> list[dict]` — 把所有工具转成 schema 列表，直接喂给模型
- 核心方法 `load_from_directory(directory: Path)`：
  1. 目录不存在直接 return（不要报错）
  2. `sorted(directory.glob("*.py"))` 遍历，跳过下划线开头的文件
  3. 用 `importlib.util.spec_from_file_location` 动态加载模块（**不能用 `import` 语句**，因为路径是运行期才知道的）
  4. **关键**：动态加载的模块必须手动塞进 `sys.modules`，否则模块内的 dataclass / 相对导入会炸
  5. `dir(module)` 遍历所有属性，找出 `issubclass(obj, BaseTool)` 且不是 `BaseTool` 本身的类
  6. 尝试实例化，失败就把异常吞掉（用户写的工具有 bug 不应该拖垮整个 Agent）

**思考题（做完再回答）**：
- 为什么 `obj is not BaseTool` 这个判断不能省？
- 为什么第 6 步要吞异常，而不是让程序崩掉？
- 如果两个文件定义了同名工具，最后生效的是哪个？（提示：看遍历顺序）

**验收**：在 `my_agent/tools/` 下放一个 `weather.py`（自己写一个假天气工具，固定返回"晴，25度"），然后：

1. 创建 `ToolRegistry`，`register` 三个内置工具
2. `load_from_directory(get_abs_path("my_agent/tools"))`
3. `list_tools()` 应该看到 4 个工具：calculator / file_read / bash / weather
4. `to_schemas()` 打印出来，检查是不是标准 function-calling 格式

### 1.4 探索式验证（不做 pytest 测试）

**现状决定（2026-09-22）**：本项目**不建 pytest 测试套件**。改用两种方式验证：

1. **ipynb 探索脚本** —— `tests/test_builtin.ipynb`、`tests/test_registry.ipynb`，手工跑、肉眼看输出
2. **固定样本文件** —— `test_data/` 下 5 个文件（txt / md / html），每次改工具后拿它们回归验证

**注意**：`tests/*.py` 里如果只是 `tool.run(...)` + `print(...)`，**pytest 一条都不会收集**（它只认 `test_` 开头的函数）。所以那些文件是探索脚本，不是测试——别把它当成"测试通过了"。

**要验证的清单**：
- `CalculatorTool`：`2+3*4` → `"14"`；`__import__('os')` → 错误开头
- `FileReadTool`：读 `test_data/` 里的文件；读不存在的路径 → 错误；空行被跳过、缩进保留
- `BashTool`：`echo hello` → 含 `hello`；报错命令 → 含 stderr 和 exit code；`ping -n 60` → 30 秒超时
- `ToolRegistry`：注册 3 个内置工具 + 加载 `my_agent/tools/` → `list_tools()` 返回 4 个

### 今晚的完成标准（自检清单）

- [x] `logger` 和 `get_abs_path` 能正常工作
- [x] `BaseTool.to_schema()` 输出符合 OpenAI function-calling 格式
- [x] 三个内置工具都能跑，错误输入返回 Error 字符串而不是崩溃
- [x] `load_from_directory` 能自动发现 `my_agent/tools/weather.py`
- [x] `list_tools()` 返回 4 个工具
- [x] **能用自己的话解释**：为什么 `run` 用 `**kwargs`、为什么动态加载要写 `sys.modules`、为什么出错返回字符串而不是抛异常

---

## 阶段 2：providers 包（09-22）

### 目标
把"调用大模型"这件事抽象出来，让 runtime 不关心底层是通义还是别的。

### 任务

**2.1 `providers/base.py` — 数据契约**

- 定义统一的消息结构：`role`（system/user/assistant/tool）、`content`、`tool_calls`
- 定义统一的响应结构：文本内容、工具调用列表、结束原因
- 用 `dataclass` 还是 `pydantic`？**建议 pydantic**，因为要解析来自 HTTP 的 JSON，自带校验
- 定义 `BaseProvider` 抽象类：`chat(messages, tools) -> Response`

**2.2 `providers/dashscope.py` — 通义千问实现**

- 用 `httpx`（异步）或 `requests`（同步）调 DashScope 的 OpenAI 兼容端点
- 端点：`https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`
- 从 `.env` 读 key，用 `python-dotenv` 加载
- 把 DashScope 的返回解析成 `base.py` 里定义的结构

**验收**：写一个一次性脚本，发一句 "你好"，打印模型的回复。

**坑点**：
- DashScope 的 tool_calls 格式和 OpenAI 完全一致，可以直接复用
- 注意 `finish_reason` 是 `tool_calls` 还是 `stop`，runtime 靠它决定要不要执行工具

---

## 阶段 3：loader 包（09-23）

### 目标
把磁盘上的 `my-agent/` 目录变成内存里的 `AgentDefinition` 对象。

### 任务

- `AgentDefinition` 数据类字段：`name / model / provider / temperature / max_tokens / instructions / skills / tools / raw_config`
- `load_agent_definition(agent_path: Path) -> AgentDefinition`：
  1. 读 `agent.yml`（**注意**：统一用 `.yml` 还是 `.yaml`？参考项目用的是 `agent.yaml`，My-Frist-Harness 用的是 `agent.yml` —— 自己定一个，但要统一）
  2. 读 `instructions.md` 作为系统提示词
  3. 扫描 `skills/` 目录，把技能文件名收进 `skills` 列表
  4. `agent.yml` 里如果写了 `tools: [calculator, weather]`，用 registry 按名字取出来
- 错误处理：文件不存在时给**清晰的中文报错**，而不是让 `yaml.safe_load` 抛原始的 `FileNotFoundError`

**验收**：加载 `my_agent/`，打印出 `AgentDefinition`，确认 tools 里确实有 calculator 等实例。

**坑点**：
- `yaml.safe_load` 返回的可能不是 dict（空文件返回 `None`），要防御
- tools 字段在 yml 里是**字符串列表**，在 dataclass 里是 **BaseTool 对象列表**，转换发生在 loader 里

---

## 阶段 4：runtime 主循环（09-24 ~ 09-25）★ 最难的部分

### 目标
实现 ReAct 循环：**推理 → 行动 → 观察 → 再推理**，直到模型不再要求调用工具。

### 任务

**4.1 骨架**

```
messages = [system_prompt] + user_input
while 轮次 < max_turns:
    response = provider.chat(messages, tools=registry.to_schemas())
    if response 没有 tool_calls:
        return response.content          # 任务完成
    messages.append(assistant 消息，带 tool_calls)
    for call in response.tool_calls:
        result = registry.get(call.name).run(**call.arguments)
        messages.append(tool 消息，内容是 result)
return "达到最大轮次限制"
```

**4.2 必须处理的问题**

- **最大轮次**：`max_turns` 默认 10，防止模型陷入死循环烧钱
- **工具不存在**：模型可能幻觉出一个不存在的工具名，要返回 `"Error: tool 'xxx' not found"`
- **工具抛异常**：`run` 外面套 try/except，把异常转成错误字符串喂回模型
- **消息历史**：tool 消息必须带上 `tool_call_id`，和 assistant 的 tool_calls 一一对应，否则 API 报错
- **日志**：每一轮都要 log 出"模型想调什么工具、参数是什么、返回了什么"，调试时这是救命的

**4.3 流式输出（可选挑战）**

如果时间够，加上流式：模型的文字一边生成一边打印，让 CLI 体验更好。

**验收**：
1. 问 "3 的 8 次方是多少" → 应该看到计算器被调用
2. 问 "帮我看看 my_agent/agent.yml 里写了什么" → 应该看到 file_read 被调用
3. 问 "今天天气怎么样" → 应该看到 weather 工具被调用（假数据）
4. 问 "1+1等于几？顺便告诉我你是谁" → 观察是否会一轮内调工具 + 回答

**坑点**：
- 模型有时会**不调用工具直接瞎编答案**，这是正常的，观察它的行为模式
- 多轮工具调用后 context 会变长，注意 token 消耗
- DashScope 要求 assistant 消息里的 tool_calls 格式完整（含 id、type、function 三段）

---

## 阶段 5：memory + agents 数据类（09-26）

### 目标
让 Agent 记住多轮对话。

### 任务

**5.1 `memory/store.py`**

- 类 `MemoryStore`，内部 `list[Message]`
- 方法：`add(message)` / `get_messages()` / `clear()` / `to_provider_format()`
- 加一个 `max_messages` 上限，超出时保留 system 消息 + 最近 N 条（**这是最朴素的上下文裁剪**）
- 挑战：把历史落盘成 JSON，下次启动能恢复

**5.2 `agents/base.py`**

- 把 `AgentDefinition`（静态配置）+ `MemoryStore`（动态状态）+ `ToolRegistry` 组合成一个 `Agent` 类
- 提供 `Agent.run(user_input) -> str`，内部委托给 runtime

**验收**：同一个 Agent 连续对话三轮，第三轮问"我刚才说了什么"，它能答上来。

---

## 阶段 6：（已跳过）CLI 命令行入口

**决定（2026-09-22）：不做 CLI。** 直接用 ipynb 驱动 runtime 和 Agent。

原因：本阶段目标是**理解每一行为什么这么写**，不是交付一个可分发的工具。CLI 的 `argparse` / 子命令分发属于工程包装，不涉及 Agent 运行时的核心概念。真正做到"能给别人用"时，入口会是阶段 7 的 FastAPI 服务。

**代价（要接受）**：项目暂时不是一个"能跑的程序"，只是个库 + 一组探索脚本。别人拿到仓库没法直接运行。

---

## 阶段 7：server + 全量测试（09-28）

### 目标
把 Agent 暴露成 HTTP API。

### 任务

- 用 FastAPI 写 `server/app.py`
- `POST /chat` 接收 `{"message": "..."}`，返回 `{"reply": "..."}`
- 应用启动时（lifespan）加载一次 Agent，复用
- 用 `uvicorn` 启动，PyCharm 里配置一个 Run Configuration

**安全加固（这一阶段回头补的）**：
- `FileReadTool` 加路径沙箱：`Path(path).resolve()` 必须落在项目根目录内，否则拒绝
- `BashTool` 加命令黑名单（至少挡掉 `rm -rf`、`format`、`shutdown`）
- 思考：黑名单的局限是什么？生产环境应该怎么做？（提示：容器隔离、只读挂载）

**验收**：
1. `uvicorn myharness.server.app:app --reload` 能起来
2. PyCharm 的 HTTP Client（`.http` 文件）或浏览器能拿到 `/chat` 的响应
3. `pytest` 全绿

---

## 阶段 8：复盘巩固（09-29 ~ 09-30）

**这两天不写新功能，只做三件事**：

1. **默写**：合上代码，从零手写 `ToolRegistry` 和 runtime 主循环，写完再对照。写不出来的地方就是没懂的地方。
2. **画图**：画出一次完整调用的时序图（用户输入 → loader → provider → tool → 回填 → 再调用 → 输出），标出每一步的数据结构。
3. **写 README**：用自己的话写清楚这个项目做什么、怎么跑、架构长什么样。能讲清楚才算真懂。

**缓冲区**：如果前面某天进度落后，用 09-30 补。不要为了赶进度跳过测试。

---

## 五、进度追踪

每完成一个阶段，把上面总览表的状态改成 ✅，并在下面记一行。

| 日期 | 实际完成 | 卡住的地方 | 明天要先解决什么 |
|------|----------|------------|------------------|
| 09-21 | 阶段 0 + 1：utils 工具、BaseTool.to_schema、三个内置工具、ToolRegistry、weather 自定义工具 | BashTool 在 Windows 上超时失效 + GBK 乱码（已解决，见附录 A） | 开始 providers 包 |
| 09-22 | 阶段 2 + 3：providers（base/dashscope）、agents/base、loader；工具扩到 5 个（+bash_tool/date_tool） | `tools` vs `tool_calls` 键名 （见附录 C）；`AgentDefinition` 缺 @dataclass；loader 三处 return 类型错乱 | 写 runtime 主循环 |
| 09-23 ~ 09-25 | 阶段 4：runtime 主循环、registry 归一成 dict 索引、`tool_call_id` 配对、工具异常转错误串 | 循环缺 `return` 导致每次跑满 `max_turns`；`get_provider` 参数顺序被 `or` 掩盖 | memory |
| 09-26 ~ 09-27 | 阶段 5：MemoryStore 按会话分桶 + 上下文裁剪 + 技能按需加载；多会话（session_id 参数化、active_skills 隔离、drop/clear 连带清理） | `skill`/`skills` 单复数静默失效；`SkillDefinition` 前向引用 `NameError`；`skill.md` vs `SKILL.md`；loader 未知字段检查因位置失效而形同虚设；3 处网络请求缺 timeout | 存储层 |
| 09-27 | **PostgreSQL 持久化**（`PostgresMemoryStore` 248 行，两表 + CASCADE 外键 + advisory lock 防并发建会话）；内存版补回（`inmemory_store.py`，接口逐方法对齐，换一行即可切换）；**输出截断续写**（`_continue_response`）；`finish_reason` 分支；dashscope 响应结构校验；Milvus 栈起容器；**首次 git 提交** | `_system_message` 每轮查库（`active_skill` 未缓存）；图片会话 400（根因疑为图片消息入 PG 后每轮重发遭图床限流，**未修**） | RAG |
| 09-28 | RAG：Milvus standalone（etcd + MinIO + milvus + Attu）已起，待建 collection / embedding / 灌数据 / `SearchDocsTool` | — | server |

---

## 附录 A：Windows 上踩过的坑（2026-09-21）

这三个坑都在 `BashTool` 里，都是 Windows 特有，**Linux 上不会遇到**，但值得记下来。

### A1. `subprocess.run(timeout=N)` 超时不生效

**现象**：设 `timeout=30`，跑 `ping -n 60`，实际 **55 秒**才返回。

**根因**：`shell=True` 在 Windows 上起的是 `cmd.exe` → `cmd.exe` 再起 `PING.EXE`。超时后 `run()` 只 kill 了 `cmd.exe`，`PING.EXE` 变成孤儿进程继续跑、还占着 stdout 管道。`run()` 卡在"等管道关闭"上，直到孤儿进程自然结束。

**解法**：改用 `Popen` 拿到 `pid`，超时后杀**整棵进程树**。

```python
process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,
                           creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
out, err = process.communicate(timeout=30)
# 超时分支里：
subprocess.run(f"taskkill /F /T /PID {process.pid}", shell=True, capture_output=True)
process.communicate()      # 排空管道，注意不加 timeout
```

**为什么必须是 `Popen` 不是 `run`**：`run()` 超时时内部杀完就抛，你**拿不到 pid**，没法清理子孙进程。

**代价**：`taskkill` 是 Windows 专有。以后部署到 Linux 要换成 `os.killpg` + `signal.SIGKILL`（阶段 7 再处理）。

### A2. 中文输出 `UnicodeDecodeError`

**现象**：`text=True` 时跑 `ping` / `ipconfig` 报 `'utf-8' codec can't decode byte 0xd5`。

**根因**：中文 Windows 控制台输出是 **GBK**，而 `text=True` 默认按 UTF-8 解码。

**解法**：不用 `text=True`，拿 bytes 自己解：

```python
stdout = result.stdout.decode("gbk", errors="replace")
```

`errors="replace"` 保证解不出来的字节变成 `�` 而不是抛异常——**工具永远不该因为编码问题崩掉**。

### A3. `shell=False` 会让 cmd 内置命令全部失效

**现象**：去掉 `shell=True` 改用 `command.split()`，跑 `echo hello` 报 `[WinError 2] 系统找不到指定的文件`。

**根因**：`echo`、`dir`、`type`、`copy` 是 **cmd.exe 的内置命令**，磁盘上根本没有 `echo.exe`。之前能跑全靠 shell 解释。

**结论**：**必须保留 `shell=True`**。`dir` 这类命令对 Agent 是刚需（模型要看目录），弃用 shell 的损失远大于收益。

### A4. Jupyter 的模块缓存陷阱

**现象**：改完 `builtin.py` 加新类，ipynb 里 `from ... import BashTool` 报 `ImportError`。

**根因**：Python 的 `import` 一旦成功，后续同名 import **直接返回内存里那份**，不读磁盘。Jupyter 内核长期存活，缓存的是旧版本。

**解法**：notebook 第一个 cell 加：

```python
%load_ext autoreload
%autoreload 2
```

---

## 附录 B：`sys.modules` 那行的真实作用（推翻了一个常见说法）

网上和参考项目的注释都说"动态加载时不写 `sys.modules` 会炸"。**实测（Python 3.13）证明这是错的**，至少对下面这种工具不成立：

```python
# weather.py
from myharness.tools.base import BaseTool   # myharness 早就被正常 import 过
```

实测结果：

| 场景 | 不写 `sys.modules` | 写 `sys.modules` |
|---|---|---|
| 只 import `myharness.tools.base` | ✅ 成功 | ✅ 成功 |
| 模块内有 `@dataclass` | ✅ 成功（老版本 Python 会炸） | ✅ 成功 |
| 同目录工具互相 import | ❌ 两种都炸 | ❌ 两种都炸 |

**唯一实测到的真实差异**：同一个文件加载两次，**会产生两个不同的类对象**。

```
mod1.WeatherTool is mod2.WeatherTool  ->  False
```

**所以那行要写，但理由是"保证模块身份唯一"**，不是"不写就崩"。后果是 `isinstance` 在跨次加载间判断失败、ipynb 里反复跑 cell 会不断生成新类。

**顺带发现**：`my_agent/tools/` 下的工具**不能互相 import**（`from myharness_dynamic_tools.helper import ...` 会报 `No module named 'myharness_dynamic_tools'`）。参考项目也这样。工具之间本就不该互相依赖，知道边界就行。

**教训**：参考代码的注释会过时，教程的解释会出错。跑一下再信。

---

## 附录 C：阶段 2 / 3 实测记录（2026-09-22）

### C1. 请求体里工具列表的键是 `tools`，不是 `tool_calls` ⚠️

```python
payload["tools"] = tools          # ✅ 正确
payload["tool_calls"] = tools     # ❌ DashScope 不报错，静默忽略
```

实测：

```
payload['tools']       ->  finish_reason='tool_calls', tool_calls=1 个     ✅
payload['tool_calls']  ->  finish_reason='stop',       tool_calls=0 个     ❌
```

**最坏的一种失败**：HTTP 200、无报错、日志正常，**工具完全不生效**。

方向要记牢：
- `tools` = 你发给模型的**菜单**（有哪些工具可用）
- `tool_calls` = 模型回给你的**点单**（要调哪些）

### C2. `arguments` 要双向转换

```
收进来：  "{\"expression\": \"123*456\"}"  --json.loads-->  {"expression": "123*456"}
发出去：  {"expression": "123*456"}        --json.dumps-->  "{\"expression\": \"123*456\"}"
```

- **provider 解析响应时** `json.loads`，所以 `ToolCall.arguments` 是 `dict`
- **provider 构造请求时** `json.dumps`，因为 API 要字符串

runtime 全程只见 `dict`，`tool.run(**call.arguments)` 直接用。

### C3. assistant 消息必须带 `tool_calls`，否则模型返回空

实测：只 append `tool` 消息、忘了 append 配对的 `assistant` 消息 →

```
回复: ''          ← 空字符串，HTTP 200，不报错
```

**静默失败，极难排查。** runtime 里 `assistant` 和 `tool` 消息必须成对 append。

### C4. 空 content 用 `[]`，不要用空 text 块

```python
content=[{"type": "text", "text": response.content}] if response.content else []   # ✅
content=[{"type": "text", "text": ""}]                                             # ⚠️ 行为反常
```

实测四种写法（`[]` / `""` / `None` / 空 text 块），前三种正常，**只有空 text 块让模型回了空字符串**。用 `[]`，语义也最准："这条消息没有正文，只有工具调用"。

### C5. `reasoning_content` 只展示，永不回传

- `enable_thinking=True` 时，思考过程在**独立的 `reasoning_content` 字段**，不混进 `content`
- 耗时差 6~8 倍（`thinking=False` 约 0.6~0.9s，`True` 约 4~6s）
- 塞回历史消息 DashScope **返回 200 不报错**，但换 OpenAI / Anthropic 会 **400**

→ `ChatResponse` 有 `reasoning` 字段；`ChatMessage` **刻意不设**这个字段。

### C6. pydantic 的可变默认值 `= []` 是安全的

**推翻了我之前的说法。** 实测：

```
pydantic:  tool_calls: list[X] = []                    -> 各实例独立，安全 ✅
dataclass: skills: list[str] = field(default_factory=list)  -> 必须这样写 ✅
```

"可变默认值共享"的坑只发生在 **dataclass 和普通函数参数**上，pydantic 内部会为每个实例拷贝。

### C7. 图片 content block 的正确格式

```python
{"type": "image_url", "image_url": {"url": "..."}}     # ✅
{"type": "image", "url": "..."}                        # ❌ 400: Invalid value: image
```

`image_url` 这个词出现三次：块类型标识 / 键名 / 里面的 `url`。

**本地图片路径不能直接用**（`file:///`、裸路径、反斜杠路径全部 400）——服务器下载不了你硬盘上的文件。必须：

```python
b64 = base64.b64encode(open(path, "rb").read()).decode()
{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
```

还要注意 **`model` 必须是视觉模型**（`qwen-vl-plus`）。非视觉模型收到图片**不报错**，只回"我无法查看图片"。

### C8. 模型倾向于自己重算，不盲信工具结果

喂给模型 `123*456 = 999`（伪造的错误结果），它回 `123 * 456 = 56088`——**自己重算了**。

含义：**测"工具调用成功"要用模型自己不知道的事**（读本地文件、查天气），用算术题看到可能只是模型自己算的。

### C9. 模型会用错工具，而不是说"我没有合适的工具"

只给 `calculator` 一个工具、问日期时，模型传了：

```
calculator({'expression': 'date'})       ← 把 "date" 当数学表达式
```

工具白名单挡住了（`Name` 节点不在白名单），返回错误字符串。**runtime 的"错误喂回模型"设计正好处理这种**——喂回去后模型应该会改口说做不到。

补上 `date_tool` 后再问，模型立刻选对：`date_tool({})`。

### C10. loader 的异常路径（验证通过）

| 情况 | 结果 |
|---|---|
| yml 里工具名拼错（`date_toola`） | warning + 跳过，其余工具正常加载，**不崩** |
| yml 是空文件 | `[配置错误] ...agent.yml 是空文件`，信息清晰 |
| 模型名写错（`qwen3.-flash`） | `HTTP 404: ...model_not_found`，**完整 API 错误透出来** |

**有效模型名**（实测）：`qwen3.7-flash`、`qwen3.8-max`、`qwen-flash`、`qwen-turbo`、`qwen-plus`、`qwen-vl-plus`、`qwen-vl-max`、`qwen3-235b-a22b-thinking-2507`
**无效**：`qwen3-flash`


---

## 六、和 My-Frist-Harness 的区别

| | My-Frist-Harness | My-Second-Harness |
|---|---|---|
| 目的 | 照着参考项目抄一遍，快速跑通 | **理解每一行为什么这么写** |
| 供应商 | DashScope | 自己选（可继续用 DashScope） |
| 配置文件名 | `agent.yml` | 你自己定，注意和 loader 保持一致 |
| 额外内容 | `utils/` 日志和路径工具 | 保留，这是好实践 |
| CLI | 有 | **跳过**（见阶段 6 说明） |
| 验证方式 | pytest | ipynb + `test_data/` 样本 |

---

## 七、后续改装路线图（手敲完成之后）

**阶段 1~7 手敲完 = 打通了主干**（工具 → 模型 → 加载 → 循环 → 记忆）。

**之后的改装不是"补功能"，是"改架构"** —— 会验证前面每一步抽象设计得对不对。下面按依赖顺序列，**顺序不能乱**（后面的依赖前面的）：

| # | 改装项 | 依赖 | 会验证/推翻什么 |
|---|---|---|---|
| 1 | **持久化**（PostgreSQL） | 无 | `MemoryStore` 接口是否真的可替换 |
| 2 | **多 Agent** | 无 | `AgentDefinition` + `ToolRegistry` 是否支持多实例并存 |
| 3 | **RAG** | 无 | 新的 `BaseTool` 子类够不够用（大概率要加工具） |
| 4 | **多租户隔离** | 1 + 2 | 数据层是否处处带 tenant 维度 |
| 5 | **前端** | 全部 | 服务端接口设计 |

### 关键设计原则（现在写代码时就该守住）

**① 数据访问必须走接口，不能直接 `list`**

改装的第 1 步就是把内存换成 PG。如果 runtime 里到处 `messages.append(...)` 直接操作列表，换 PG 时要改一片。

→ **阶段 5 的 `MemoryStore` 就是那道防线**：runtime 只调 `store.add()` / `store.get_messages()`，**永远不碰内部结构**。

**② 所有数据都要能归属到某个"会话"和某个"租户"**

多租户是第 4 步，但如果数据模型一开始没有 tenant 维度，后面加要动全部表 + 全部查询。

→ 现在就想好：一条消息至少属于 `(tenant_id, session_id)`。哪怕现在只写死 `"default"`。

**③ 工具要能按 agent 裁剪**

你已经做了（`agent.yml` 里显式列 `tools`）。多 Agent 场景下这是**安全边界**——不同 agent 拿不同工具，而不是靠提示词约束。

**④ 检索（RAG）本质上也是一个工具**

不要把它做成"框架内置功能"。做成 `BaseTool` 的子类（比如 `SearchDocsTool`），那么：
- 模型自己决定什么时候查
- 可以按 agent 配置开关
- 不需要改 runtime

→ 这条也是对你 `BaseTool` 抽象的检验：**如果 RAG 不能干净地做成一个工具，说明工具抽象漏了东西。**

### 现在不做的事

- **PostgreSQL**：runtime 都还没写，没有多轮对话要存。等主干通了再上。
- **langchain**：已于 2026-09-22 移除（`uv remove langchain langchain-openai`）。手搓的 `BaseProvider` / `ChatResponse` / ReAct 循环已是同类替代，且更透明。

---

## 附录 D：阶段 4 / 5 实测记录（2026-09-24 ~ 09-27）

### D1. `Popen` 必须保留 `shell=True`（Windows 专有坑）

弃用 `shell=True` 改用列表传参后，`echo` / `dir` / `type` 等 **cmd 内置命令全部失效**（`[WinError 2] 系统找不到指定的文件`）——这些不是独立可执行文件，磁盘上没有 `echo.exe`。

**保留 shell 的代价**是超时时必须手动杀进程树（见附录 A1），**但 `dir` 对 Agent 是刚需**，取舍明确。

### D2. `payload["tool_calls"]` 静默失效

见附录 C1。补充实测：DashScope **不报错**，`finish_reason` 变成 `stop`，工具完全不生效。

**这是最坏的一种失败**——HTTP 200、日志正常、模型照常回答（自己算的），你根本看不出工具没被调用。

### D3. 循环缺 `return` → 每次跑满 `max_turns` ⚠️

```python
if not response.tool_calls:
    logger.info(f"[完成] {_} 轮")     # 打了"完成"却不返回
    # ← 缺 return response
```

**症状**：日志里明明有 `[完成] 1 轮`，但 `res.content` 永远是"错误：达到最大迭代次数"。因为循环继续转到 10 轮，落到兜底返回。

**教训**：日志说"完成"但返回值不对 → **先检查是不是漏了 return**，别急着怀疑模型。

### D4. `get_provider` 参数顺序被 `or` 掩盖

```python
self.provider = provider or get_provider(self.definition.model, self.definition.provider)
#               ↑ 默认值 "dashscope" 是真值，get_provider 永远不执行
```

函数签名是 `(provider, model)`，调用传的是 `(model, provider)`。**只要 `provider` 参数有值，这个 bug 就永远不暴露。**

两个都是 `str` 类型的参数最容易出这种事——**用关键字实参**（`get_provider(provider_name=..., model=...)`）能彻底消掉。

### D5. `self.x = list[ChatMessage]` 不是空列表

`list[ChatMessage]` 是 **`types.GenericAlias` 对象**（3.9+ 的类型注解写法），不是 `[]`。

```python
self._memory: list[ChatMessage] = []     # ✅  冒号是注解，等号才赋值
self._memory = list[ChatMessage]         # ❌  赋了个类型对象
```

报错是 `TypeError: descriptor 'append' for 'list' objects doesn't apply to a 'ChatMessage' object`——**完全指不到病因**。

### D6. `agent.yml` 键名单复数不一致 → 静默加载 0 个

```yaml
skill:            # yml 里写单数
  - partner
```
```python
for name in config.get("skills", []):    # 代码读复数 → 拿到 []，循环不执行
```

**没有任何报错**，只是技能"不见了"。

**防御**（值得加进 loader）：

```python
known = {"name", "model", "provider", "temperature", "max_tokens",
         "enable_thinking", "instructions", "skills", "tools"}
unknown = set(config.keys()) - known
if unknown:
    logger.warning(f"[配置] agent.yml 里有无法识别的字段: {unknown}")
```

这条 warning 会直接抓到 `{'skill'}`。**配置解析的通用原则：未知键要么报错要么警告，绝不静默忽略。**

### D7. dataclass 类型注解在**类定义时**求值

```python
@dataclass
class AgentDefinition:
    skills: list[SkillDefinition] = ...     # NameError（SkillDefinition 还没定义）

@dataclass
class SkillDefinition: ...
```

实测：`NameError: name 'SkillDefinition' is not defined`。

**解法**：被引用的类**定义在前面**。或者写成字符串 `list["SkillDefinition"]` 延迟求值。

（对比：pydantic 的 `BaseModel` 没这个问题，它会延迟解析注解。这是 dataclass 和 pydantic 的一个实际差异。）

### D8. 上下文裁剪：必须保住 assistant / tool 配对

`tool` 消息的 `tool_call_id` 指向 `assistant` 消息里某次调用。**按条数硬砍头部会切断配对**——留下孤立的 `tool` 消息，其 `tool_call_id` 成为悬空引用（OpenAI 直接 400）。

**解法**：以 `role == "user"` 为切割点整轮丢（`user` 天然是一轮对话的开头）。

两个实现要点：
- 从**索引 1** 开始找切割点（索引 0 若是 `user`，以它切割等于没切，下次 `add` 又触发，空转）
- **找不到就放弃**（历史全是 tool/assistant 时怎么切都断配对，宁可暂时超限）

### D9. 技能按需加载：索引常驻，正文按需

**收益实测**：

| | 系统提示词长度 |
|---|---|
| 技能全文注入 | 约 4500 字 |
| 只有索引（name + description） | **892 字** |

**结构**：

```
agent.yml:  skills: [partner]                    ← 显式声明，不扫目录
skills/partner/SKILL.md:  frontmatter(name/description) + 正文
系统提示词: 只放 name + description
模型判断需要 → 调 read_skill(name) → 正文才进上下文
```

**这个结构和 RAG 同构**："索引常驻 + 按需检索"，只是检索靠模型读描述判断，而非向量相似度。改装阶段接向量库时，换的是检索方式，不是整个机制。

**验证比"能读到"更重要的是"不该读时不读"**：

```
场景 1「今天有点累，想跟你说说话」→ 日志出现 read_skill({'name': 'partner'}) ✓
场景 2「算一下 12*34」           → 日志【没有】read_skill，直接调 calculator ✓
```

只验证场景 1 不够——如果模型干什么都先读一遍技能，省 token 的设计就白做了。

**调优旋钮**：`SKILL.md` 的 `description` + `ReadSkillTool.description`。写太泛每次都读，写太窄该读不读。

### D10. 跨平台文件名大小写

`SKILL.md`（大写）vs `skill.md`（小写）——**Windows 文件系统不区分大小写，Linux 区分**。

本机跑通不代表部署能跑。同类问题还有：`BashTool` 里的 `taskkill`（Windows 专有）、`open()` 不指定 `encoding`（Windows 中文系统默认 GBK）。

**部署前要过一遍这三处。**

---

## 附录 E：多会话 + 技能按需加载的最终形态（2026-09-27）

### E1. 会话状态放在哪 —— 一张表说清

| 状态 | 存在哪 | 按会话分吗 |
|---|---|---|
| 消息历史 | `MemoryStore._sessions: dict[str, list[ChatMessage]]` | ✅ 按 session_id 分桶 |
| 当前技能 | `AgentRuntime.active_skills: dict[str, str]` | ✅ 按 session_id 分 |
| 最后用的 id | `AgentRuntime.last_session_id` | 单个值（不传 id 时靠它找回来） |
| 工具实例、provider、系统提示词 | `AgentRuntime` 实例属性 | ❌ 全局共用（无状态） |

**一个 `AgentRuntime` 服务所有会话**，靠参数 `session_id` 路由。

### E2. 状态分散的代价：清理时必须记着两处

```python
def drop_session(self, session_id: str) -> None:
    self.memory.drop_session(session_id)          # 清消息
    self.active_skills.pop(session_id, None)      # 清技能 ← 容易漏
    if self.last_session_id == session_id:
        self.last_session_id = None
```

**为什么不能只在 `MemoryStore` 里清**：`active_skills` 是 runtime 的状态，store 碰不到它（跨了抽象边界）。**漏清的后果**：删了 1000 个会话，`active_skills` 里留 1000 个僵尸条目，一直涨。

**这是"状态分散在两处"的必然代价。** 等状态涨到五六个（`tenant_id`、`user_id`、创建时间……），就该把它们收拢成一个 `Session` 对象——**多租户那步自然会做**。

### E3. `SessionManager` 被删掉了 —— 记录下来为什么

最初的设想是一层 `SessionManager` 管"会话 → runtime 实例"的映射。**重构后被证明是多余的**：

- 改成 `session_id` 参数化之后，一个 runtime 就能服务所有会话
- 那层只剩"查 dict"，而 dict 已经在 `MemoryStore` 里了
- 变成同一件事的第二个封装

**判断依据**：新加的一层如果只是转发调用、不增加任何职责，就不该存在。它会在**多 Agent**（不同会话用不同 `agent.yml`）那一步重新出现——那时候它才有实在的职责。

### E4. `session_id` 生成策略

```python
# 不传就新建
if session_id is None:
    session_id = uuid.uuid4().hex[:16]
```

**为什么是 16 位而不是 8 位**：这是生日悖论。8 位十六进制 = 32 bit，看着有 40 亿种组合，但**约 4 万**个会话时就有 50% 概率撞上任意两个。撞了的后果是**两个用户的历史混在一起**，极难排查。16 位 = 64 bit，阈值到了 50 亿量级，实际不可能撞。

**注意 `.hex`** —— 不带横线的干净十六进制串。`str(uuid4())[:16]` 会把带横线的版本切一半。

### E5. 上下文裁剪：必须保住 assistant / tool 配对

`tool` 消息的 `tool_call_id` 指向 `assistant` 消息里某次调用。**按条数硬砍头部会切断配对** → 孤立的 `tool` 消息 + 悬空引用（OpenAI 直接 400）。

**解法**：以 `role == "user"` 为切割点整轮丢。

两个实现要点：
- 从**索引 1** 开始找切割点（索引 0 若是 `user`，以它切等于没切，下次又触发，空转）
- **找不到就放弃**（全是 tool/assistant 时怎么切都断配对，宁可暂时超限）

**实测**：`max_messages=20` 时塞 32 条 → 剩 20 条，且首条是 `user` ✓

### E6. 技能按需加载：从"模型自主"改成"调用方控制"

**演进过程**（三个阶段，都被实测推着走）：

| 版本 | 谁决定用技能 | 正文怎么进上下文 | 问题 |
|---|---|---|---|
| 1. 全量注入 | 无（总是） | 拼进系统提示词 | 4500 字常驻，技能多了爆炸 |
| 2. 工具加载 | **模型**调 `read_skill` | 作为 `tool` 消息进 memory | 正文永久占用上下文，每轮重发 |
| 3. **调用方传参**（现） | **调用方** `run(skill=...)` | 每轮临时拼进系统提示词 | 无 |

**版本 3 的关键机制**：

```python
rt.run(msg, session_id="a", skill="partner")     # 调用方指定
    ↓  self.active_skills["a"] = "partner"
_system_message("a")                              # 每轮现读磁盘、现拼
    ↓
messages = [system(含技能正文)] + memory历史       # 正文在 system，不落 memory
```

**收益**：
- **正文不进 memory** → 不占历史预算、不被裁剪、不每轮重发
- **模型没有自主权** → 不会"该读不读"或"乱读"
- **改 `SKILL.md` 立即生效**（每次重读磁盘），调试方便

**代价**：每轮读一次磁盘（几 KB，可忽略）；`active_skill` 粘住（不传就沿用，想换要显式传新名字）。

**模型能力的边界**：技能索引**不再进系统提示词**——模型不知道技能存在，自然不会试图调用。这是刻意的，避免"告诉它有能力、又不给加载途径"的误导。

### E7. 数据流全景（最终版）

```
调用方: rt.run(msg, session_id="a", skill="partner")
   │
   ├─ session_id 为空 → uuid4().hex[:16] 新建
   ├─ 记录 active_skills["a"] = "partner"
   │
   └─ 循环（最多 max_turns 轮）
        │
        ├─ messages = [system(基础提示词 + 技能正文)] + memory.get_messages("a")
        │                                              ↑ 正文现读现拼，不进 memory
        ├─ provider.invoke(messages, tools)
        │
        ├─ finish_reason == "length" → WARNING 记录截断，但仍返回（不假装完成）
        ├─ finish_reason == "stop"   → INFO 完成
        ├─ 其他                       → WARNING 未知原因
        │
        └─ 有 tool_calls？
             ├─ 无 → return response
             └─ 有 → 执行工具，assistant + tool 消息成对写入 memory，继续循环
```

---

## 附录 F：待办清单（截至 2026-09-27）

### 手敲主干未完成

| | 项 | 说明 |
|---|---|---|
| 1 | `server/app.py` | FastAPI + `/chat`，用 `lifespan` 加载一次 Agent；`session_id` 从请求体来 |
| 2 | 安全加固 | `FileReadTool` 路径沙箱（`resolve()` + `is_relative_to`）；`BashTool` 命令黑名单（**注意：黑名单不是安全保障**） |
| 3 | `README.md` | 0 字节。至少要写"是什么 + 怎么跑 + 架构" |

### 已知问题（未处理，按优先级）

| | 问题 | 影响 |
|---|---|---|
| 1 | **输出截断不续写** | `finish_reason == "length"` 时只记 WARNING 就返回半句话。**实测模型收到"继续"会从头重写**，只有明确说"不要重复"的措辞才接续——续写功能要实现得配合重叠检测，成本较高 |
| 2 | 没有 git | 1000+ 行手写代码无版本历史。`.gitignore` 已备好，`git init` 随时可做 |
| 3 | `SKILL.md` frontmatter 解析写了两遍 | `loader.load_skill_definition` 和 `runtime._system_message` 各一份。**已经因此出过 off-by-one bug**（`> 3` 应为 `>= 3`，导致技能正文恒为空） |
| 4 | 工具命名不统一 | `calculator` / `file_read` vs `bash_tool` / `date_tool` / `location_tool` |
| 5 | `DateTool` / `LocationTool` 声明了用不上的参数 | 模型会老实传，然后被静默忽略 |
| 6 | `memory/store.py` 的 `get_talk_turns()` | 无调用方 |
| 7 | `agents/base.py` 的 `raw_config: dict = None` | 类型注解不实 |

### 已修（本轮）

- ✅ loader 未知字段检查位置错误 —— 原本放在 `for name in config.get("skills", [])` 循环体内，**恰好在它该抓的"`skill` 写成单数"场景下失效**（循环不执行 → 检查不跑）。已提到 yml 校验之后，常量化为 `KNOWN_CONFIG_KEYS`
- ✅ 3 处网络请求缺 `timeout` —— `weather.py` 两处（`requests.get` 默认**永久等待**）、`LocationTool` 第二处。**这类挂起会冻住整个 `run()`，`max_turns` 管不到**
- ✅ `runtime` 不区分 `finish_reason` —— 实测 `'length'`（截断）时日志写 `[完成]`，静默把半句话当完整回复。已分 `stop` / `length` / 其他三支
- ✅ `dashscope` 直接访问 `data["choices"][0]["message"]` —— `KeyError` / `IndexError` 完全看不出病因。已改为 `.get()` + `isinstance` 校验，异常时把**完整响应原文**打进日志

---

## 附录 G：存储层的可替换性（2026-09-27）

### G1. 两个实现，一套接口

```
memory/inmemory_store.py   MemoryStore         112 行  测试 / 无库环境
memory/postgres_store.py   PostgresMemoryStore 248 行  生产
```

**9 个方法签名逐个对齐**（用 `inspect.signature` 比对验证过）：

| 方法 | 作用 |
|---|---|
| `add(session_id, message)` | 追加消息 |
| `get_messages(session_id)` | 读该会话全部消息（返回副本） |
| `get_talk_turns(session_id)` | 用户说了几轮 |
| `message_count(session_id)` | 消息条数 |
| `get_active_skill(session_id)` | 该会话当前技能 |
| `set_active_skill(session_id, skill)` | 设置技能 |
| `list_sessions()` | 全部会话 id |
| `drop_session(session_id)` | 删一个会话 |
| `clear()` | 删全部 |

**唯一差异在 `__init__`**：内存版 `dsn` / `agent_id` 给了默认值（用不上），PG 版必填。切到 PG 时参数自然传得进去。

### G2. PG 的 schema 顺手消掉了一个设计债

```sql
harness_sessions (agent_id, session_id, active_skill, created_at, updated_at)
    PRIMARY KEY (agent_id, session_id)

harness_messages (id, agent_id, session_id, message JSONB, created_at)
    FOREIGN KEY (agent_id, session_id) REFERENCES harness_sessions ON DELETE CASCADE
```

**`active_skill` 从 runtime 的 dict 挪进了表里** —— 于是"删会话要清两处状态"的问题**从结构上消失了**：`DELETE FROM harness_sessions` 一行，消息由 `CASCADE` 带走，技能随行消失。**不可能漏清。**

对比重构前：`MemoryStore._sessions` + `AgentRuntime.active_skills` 两个 dict，`drop_session` 要记得清两个 —— 靠人记。

### G3. `_ensure_session` 的并发防护

```python
row = conn.execute("SELECT 1 FROM harness_sessions WHERE ...")   # 先查
if row: return
conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (self.agent_id,))
row = conn.execute("SELECT 1 FROM harness_sessions WHERE ...")   # 加锁后再查
if row: return
# 才 INSERT
```

**双重检查 + advisory lock** —— 两个请求同时建同一会话时，只有一个能插进去。**这是防并发的标准写法**，值得记住这个模式。

---

## 附录 H：待办（截至 2026-09-28）

### RAG（进行中）

| | 步骤 | 状态 |
|---|---|---|
| 1 | Milvus standalone + Attu 起容器 | ✅ |
| 2 | 连上 Milvus，建 collection | ⬜ |
| 3 | embedding 调用（DashScope `text-embedding-v3`？） | ⬜ |
| 4 | 灌数据：`test_data/` → 切块 → 向量 → 入库 | ⬜ |
| 5 | `SearchDocsTool(BaseTool)`，加进 `agent.yml` | ⬜ |

**架构原则**（ROADMAP 第七节定过）：**RAG 就是一个 `BaseTool` 子类**，不做成框架内置功能。runtime / providers / memory / loader **一行都不用改**。

**语料候选**：`test_data/` 5 个文件（约 16KB），或 `ROADMAP.md` 自身。

### 已知未修

| | 问题 | 影响 |
|---|---|---|
| 1 | **图片会话 400** | 图片消息入 PG 后**每轮重发**，图床限流导致偶发 `URL does not appear to be valid`。根因是"图片进了 history 就一直重发" |
| 2 | `_system_message` 每轮查库 | 已经把 `active_skill` 提到循环外 + 改签名收技能名，**待确认是否已改** |
| 3 | 没有 git | `.gitignore` 已备好 |
| 4 | `SKILL.md` frontmatter 解析写两遍 | `loader.load_skill_definition` 和 `runtime._system_message` 各一份，**已因此出过一次 off-by-one** |
| 5 | 工具命名不统一 | `calculator` / `file_read` vs `bash_tool` / `date_tool` / `location_tool` |
| 6 | `DateTool` / `LocationTool` 空参数 | 声明了用不上的参数，模型会老实传然后被忽略 |
| 7 | `README.md` 0 字节 | — |
| 8 | `server/app.py` 0 字节 | — |
| 9 | 安全加固未做 | `FileReadTool` 路径沙箱、`BashTool` 黑名单 |

### 基础设施

```
docker-compose.yml 里现有：
  harness-postgres       5433   PG 持久化
  harness-milvus-etcd      -    Milvus 元数据
  harness-milvus-minio     -    Milvus 对象存储
  harness-milvus         19530  Milvus 本体
  harness-attu           8001   Milvus Web GUI

端口预留：8000 留给未来的 FastAPI server
```

### 记忆点

- **内存版重启就丢**，这是它的本分。要"重启还在"必须用 PG
- **Attu 是"看"的工具**，不是"改"的 —— 建库建表该写代码，才可复现
- **Milvus Lite 支持 Windows**（纯 Python wheel），如果 Docker 太重可以换
