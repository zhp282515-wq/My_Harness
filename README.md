# My Harness

一个以文件目录作为 Agent 定义的 Python Harness。它可以读取 Agent 配置、系统指令、技能和自定义工具，通过 DashScope 兼容接口调用大模型，并用工具调用循环处理任务。对话记录保存在 PostgreSQL。

## 功能

- 从 `my_agent/agent.yml` 加载模型、提示词、技能和工具
- 使用 DashScope 兼容 API（示例模型：`qwen3.7-flash`）
- 支持计算器、文件读取、日期、位置、天气等工具
- 将会话与消息持久化到 PostgreSQL
- 解析 TXT、Markdown、PDF、DOCX 和 XLSX，并把文档切分为带来源信息的文本块
- 提供 Milvus 向量存储的初始接口

## 环境要求

- Python 3.13 或更高版本
- [uv](https://docs.astral.sh/uv/)（推荐）或 pip
- Docker Compose（用于 PostgreSQL；Milvus 仅在需要向量数据库时使用）
- DashScope API Key

## 安装与配置

```bash
git clone https://github.com/zhp282515-wq/My_Harness.git
cd My_Harness
uv sync
```

创建本地环境配置文件：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

在 `.env` 中填入 DashScope API Key，并启动 PostgreSQL：

```dotenv
DASHSCOPE_API_KEY=替换成你的_API_Key
POSTGRES_USER=my_harness
POSTGRES_PASSWORD=change-me-for-local-dev
POSTGRES_DB=my_harness
DATABASE_URL=postgresql://my_harness@localhost:5433/my_harness
PGPASSWORD=change-me-for-local-dev
```

```bash
docker compose up -d postgres
```

Compose 中的 PostgreSQL 默认凭据仅用于本地开发。部署时应设置自己的数据库和凭据；`.env` 不会提交到 Git。`PGPASSWORD` 会被 PostgreSQL 客户端库用于本地连接。

## 运行 Agent

在项目根目录创建 `run_agent.py`：

```python
from myharness.providers.base import ChatMessage
from myharness.runtime import AgentRuntime

agent = AgentRuntime(path="my_agent")
reply = agent.run(
    ChatMessage(role="user", content=[{"type": "text", "text": "你好"}]),
    session_id="demo-session",
)
print(reply.content)
```

运行：

```bash
uv run python run_agent.py
```

Agent 目录由 `agent.yml`、`instructions.md`、可选的 `skills/` 和 `tools/` 组成。可以复制 `my_agent/` 并按需修改。初始化 `AgentRuntime` 时会连接 PostgreSQL；调用模型时需要有效的 `DASHSCOPE_API_KEY`。

## 文档解析与切分

```python
from myharness.fileparser import parse_document
from myharness.vector.splitter import DocumentSpliter

document = parse_document("path/to/document.pdf")
chunks = DocumentSpliter(chunk_size=500, overlap=100).split(document)
```

解析器支持 `.txt`、`.md`、`.markdown`、`.pdf`、`.docx` 和 `.xlsx`。PDF、Word 和 Excel 解析器会提取页面、段落、表格或工作表内容。Word 分页依赖 Windows 上安装的 Microsoft Word；其他平台使用解析器提供的降级处理。Excel 表头格式不明确时可能需要手动指定表头行。

## Milvus（可选）

需要本地 Milvus 时启动 Compose 中的依赖服务：

```bash
docker compose up -d etcd minio milvus
```

`VectorStoreService` 当前仍是接口框架，文档入库、检索和删除方法尚未实现；可以使用文档解析和切分功能。

## 项目结构

```text
myharness/
├── agents/       # Agent 配置数据结构
├── memory/       # 内存与 PostgreSQL 会话存储
├── providers/    # 模型 Provider
├── tools/        # 内置工具与工具注册
├── vector/       # 文档切分与 Milvus 接口
├── loader.py     # 加载 Agent 目录
└── runtime.py    # 对话与工具调用循环
my_agent/         # 示例 Agent
utils/            # 文档解析、路径和日志工具
```

## 当前限制

- `myharness/server/app.py` 尚未实现 HTTP 服务；目前通过 Python 调用 `AgentRuntime`。
- Milvus 向量存储尚不能完成向量入库或检索。
- 测试文档、Notebook 和临时探索材料不包含在发布仓库中。

## 开发

依赖由 `pyproject.toml` 管理，`uv.lock` 锁定依赖版本。运行时日志、环境变量文件、`data/`、`tmp/`、`test_data/` 和探索性测试材料均由 Git 忽略。
