"""内存版会话存储 —— 与 PostgresMemoryStore 接口完全一致，可直接替换。

用途：单元测试、快速试验、无数据库环境下跑通流程。
切换方式（runtime.py）：

    from myharness.memory.memory_store import MemoryStore
    self.memory = MemoryStore()

    # 换成 PG 只需改这一行：
    # self.memory = PostgresMemoryStore(dsn=dsn, agent_id=str(self.agent_path.resolve()))
"""

from myharness.providers.base import ChatMessage
from utils.logger_tool import logger


class InMemoryStore:
    """内存实现。

    内部结构镜像 PG 的两张表：
        _sessions  ~  harness_sessions （session_id -> active_skill）
        _messages  ~  harness_messages （session_id -> 该会话的消息列表）
    """

    def __init__(
        self,
        dsn: str | None = None,          # 内存版不需要，仅为接口兼容保留
        agent_id: str | None = None,     # 同上
        max_messages: int = 100,
        max_sessions: int = 1000,
    ) -> None:
        self.dsn = dsn
        self.agent_id = agent_id
        self.max_messages = max_messages
        self.max_sessions = max_sessions

        self._sessions: dict[str, str | None] = {}          # session_id -> active_skill
        self._messages: dict[str, list[ChatMessage]] = {}   # session_id -> messages

    # ---------------- 内部 ----------------

    def _ensure_session(self, session_id: str) -> None:
        """会话不存在就建一个。超过上限则拒绝。"""
        if session_id in self._sessions:
            return
        if len(self._sessions) >= self.max_sessions:
            logger.error(f"[记忆] 会话数已达上限 {self.max_sessions}，拒绝新建 {session_id}")
            raise RuntimeError(f"会话数已达上限 {self.max_sessions}")
        self._sessions[session_id] = None
        self._messages[session_id] = []

    def _trim(self, session_id: str) -> None:
        """按 user 消息边界裁剪，保住 assistant / tool 的配对。"""
        messages = self._messages[session_id]
        if len(messages) <= self.max_messages:
            return

        cut = next(
            (
                index
                for index, message in enumerate(messages)
                if index > 0 and message.role == "user"
            ),
            None,
        )
        if cut is None:
            logger.warning(f"[裁剪] {session_id} 找不到安全切割点，暂时保留 {len(messages)} 条")
            return

        logger.info(f"[裁剪] {session_id} 削掉前 {cut} 条，剩余 {len(messages) - cut} 条")
        del messages[:cut]

    # ---------------- 消息 ----------------

    def add(self, session_id: str, message: ChatMessage) -> None:
        self._ensure_session(session_id)
        self._messages[session_id].append(message)
        logger.debug(f"[记忆] {session_id} +{message.role} 共 {len(self._messages[session_id])} 条")
        self._trim(session_id)

    def get_messages(self, session_id: str) -> list[ChatMessage]:
        return list(self._messages.get(session_id, []))

    def get_talk_turns(self, session_id: str) -> int:
        return sum(1 for m in self._messages.get(session_id, []) if m.role == "user")

    def message_count(self, session_id: str) -> int:
        return len(self._messages.get(session_id, []))

    # ---------------- 技能 ----------------

    def get_active_skill(self, session_id: str) -> str | None:
        return self._sessions.get(session_id)

    def set_active_skill(self, session_id: str, skill: str | None) -> None:
        self._ensure_session(session_id)
        self._sessions[session_id] = skill

    # ---------------- 会话 ----------------

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())

    def drop_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._messages.pop(session_id, None)

    def clear(self) -> None:
        n = len(self._sessions)
        self._sessions.clear()
        self._messages.clear()
        logger.info(f"[记忆] 已清空全部 {n} 个会话")
