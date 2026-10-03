import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from myharness.providers.base import ChatMessage
from utils.logger_tool import logger


class PostgresMemoryStore:
    def __init__(
        self,
        dsn: str,
        agent_id: str,
        max_messages: int = 100,
        max_sessions: int = 1000,
    ) -> None:
        if not dsn:
            raise ValueError("缺少 DATABASE_URL")
        if not agent_id:
            raise ValueError("agent_id 不能为空")

        self.dsn = dsn
        self.agent_id = agent_id
        self.max_messages = max_messages
        self.max_sessions = max_sessions
        self._init_schema()

    def _connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS harness_sessions (
                    agent_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    active_skill TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (agent_id, session_id)
                )
            """)
            # CREATE TABLE IF NOT EXISTS does not add columns to an existing table.
            # Keep existing databases compatible when active_skill is introduced.
            conn.execute("""
                ALTER TABLE harness_sessions
                ADD COLUMN IF NOT EXISTS active_skill TEXT
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS harness_messages (
                    id BIGSERIAL PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    message JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    FOREIGN KEY (agent_id, session_id)
                        REFERENCES harness_sessions (agent_id, session_id)
                        ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_harness_messages_session
                ON harness_messages (agent_id, session_id, id)
            """)

    def _ensure_session(self, conn, session_id: str) -> None:
        row = conn.execute(
            """
            SELECT 1 FROM harness_sessions
            WHERE agent_id = %s AND session_id = %s
            """,
            (self.agent_id, session_id),
        ).fetchone()
        if row:
            return

        # 只在创建新会话时串行检查数量上限。
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (self.agent_id,),
        )

        row = conn.execute(
            """
            SELECT 1 FROM harness_sessions
            WHERE agent_id = %s AND session_id = %s
            """,
            (self.agent_id, session_id),
        ).fetchone()
        if row:
            return

        count = conn.execute(
            "SELECT count(*) AS n FROM harness_sessions WHERE agent_id = %s",
            (self.agent_id,),
        ).fetchone()["n"]

        if count >= self.max_sessions:
            raise RuntimeError(f"会话数已达上限 {self.max_sessions}")

        conn.execute(
            """
            INSERT INTO harness_sessions (agent_id, session_id)
            VALUES (%s, %s)
            """,
            (self.agent_id, session_id),
        )

    def add(self, session_id: str, message: ChatMessage) -> None:
        with self._connect() as conn:
            self._ensure_session(conn, session_id)

            conn.execute(
                """
                INSERT INTO harness_messages (agent_id, session_id, message)
                VALUES (%s, %s, %s)
                """,
                (
                    self.agent_id,
                    session_id,
                    Jsonb(message.model_dump(mode="json")),
                ),
            )
            conn.execute(
                """
                UPDATE harness_sessions SET updated_at = now()
                WHERE agent_id = %s AND session_id = %s
                """,
                (self.agent_id, session_id),
            )

            rows = conn.execute(
                """
                SELECT id, message FROM harness_messages
                WHERE agent_id = %s AND session_id = %s
                ORDER BY id
                """,
                (self.agent_id, session_id),
            ).fetchall()

            if len(rows) > self.max_messages:
                # 与现有 MemoryStore 一样，在后续 user 消息处切轮次。
                cut = next(
                    (
                        index
                        for index, row in enumerate(rows)
                        if index > 0 and row["message"].get("role") == "user"
                    ),
                    None,
                )

                if cut is not None:
                    old_ids = [row["id"] for row in rows[:cut]]
                    conn.execute(
                        """
                        DELETE FROM harness_messages
                        WHERE agent_id = %s AND session_id = %s
                          AND id = ANY(%s)
                        """,
                        (self.agent_id, session_id, old_ids),
                    )

    def get_messages(self, session_id: str) -> list[ChatMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT message FROM harness_messages
                WHERE agent_id = %s AND session_id = %s
                ORDER BY id
                """,
                (self.agent_id, session_id),
            ).fetchall()

        return [ChatMessage.model_validate(row["message"]) for row in rows]

    def get_active_skill(self, session_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT active_skill FROM harness_sessions
                WHERE agent_id = %s AND session_id = %s
                """,
                (self.agent_id, session_id),
            ).fetchone()
        return row["active_skill"] if row else None

    def set_active_skill(self, session_id: str, skill: str | None) -> None:
        with self._connect() as conn:
            self._ensure_session(conn, session_id)
            conn.execute(
                """
                UPDATE harness_sessions
                SET active_skill = %s, updated_at = now()
                WHERE agent_id = %s AND session_id = %s
                """,
                (skill, self.agent_id, session_id),
            )

    def get_talk_turns(self, session_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT count(*) AS n FROM harness_messages
                WHERE agent_id = %s AND session_id = %s
                  AND message->>'role' = 'user'
                """,
                (self.agent_id, session_id),
            ).fetchone()
        return row["n"]

    def list_sessions(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id FROM harness_sessions
                WHERE agent_id = %s ORDER BY created_at
                """,
                (self.agent_id,),
            ).fetchall()
        return [row["session_id"] for row in rows]

    def message_count(self, session_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT count(*) AS n FROM harness_messages
                WHERE agent_id = %s AND session_id = %s
                """,
                (self.agent_id, session_id),
            ).fetchone()
        return row["n"]

    def drop_session(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                DELETE FROM harness_sessions
                WHERE agent_id = %s AND session_id = %s
                """,
                (self.agent_id, session_id),
            )
        # 消息通过外键 ON DELETE CASCADE 一并删除。

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM harness_sessions WHERE agent_id = %s",
                (self.agent_id,),
            )