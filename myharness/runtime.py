from dotenv import load_dotenv
load_dotenv(override=True)

from myharness.providers.dashscope import DashScopeProvider
from myharness.providers.base import ChatMessage, ToolCall, ChatResponse
from utils.logger_tool import logger
from myharness.loader import load_agent_definition
from utils.path_tool import get_abs_path
from pathlib import Path
import uuid
import os
from myharness.memory.postgres_store import PostgresMemoryStore
from myharness.memory.inmemory_store import InMemoryStore
dsn = os.getenv("DATABASE_URL")


def get_provider(provider: str, model: str):

    providers = {
        "dashscope": DashScopeProvider,
    }

    cls = providers.get(provider)
    if cls is None:
        logger.error(f"未知 provider: {provider}")
        raise Exception(f"未知 provider: {provider}")

    return cls(
        model=model,
    )


class AgentRuntime:
    def __init__(
            self,
            path: str,# 传相对路径
            max_turns: int = 10,
    ):
        self.agent_path = Path(get_abs_path(path))
        self.definition = load_agent_definition(self.agent_path)
        self.provider = get_provider(self.definition.provider, self.definition.model)
        self.max_turns = max_turns
        self.tools = {tool.name: tool for tool in self.definition.tools}
        self.prompt = self._build_system_prompt()
        self.memory = PostgresMemoryStore(
            dsn=dsn,
            agent_id=str(self.agent_path.resolve()),
        )
        self.skills = {s.name: s for s in self.definition.skills}
        self.last_session_id: str | None = None

    def _build_system_prompt(self) -> str:
        return self.definition.instructions

    def _get_tool_schemas(self) -> list[dict]:
        schemas = []
        for tool in self.definition.tools:
            schemas.append(tool.to_schema())
        return schemas

    def _execute_tool(self, tool_call: ToolCall) -> str:
        name = tool_call.name
        tool = self.tools.get(name)
        if tool is None:
            logger.error(f"错误：工具 '{name}' 不存在")
            return f"错误：工具 '{name}' 不存在"
        try:
            params = tool_call.arguments
            return tool.run(**params)
        except Exception as e:
            logger.error(f"错误：执行工具 '{name}' 失败 — {e}")
            return f"错误：执行工具 '{name}' 失败 — {e}"

    def _system_message(self, skill_name: str | None) -> ChatMessage:
        text = self.prompt
        if skill_name:                              # ← 不再查库
            sd = self.skills.get(skill_name)
            if sd:
                parts = sd.path.read_text(encoding="utf-8").split("---", 2)
                body = parts[2] if len(parts) >= 3 else parts[0]
                text += f"\n\n## 当前技能指令\n{body}"

        return ChatMessage(role="system", content=[{"type": "text", "text": text}])

    def drop_session(self, session_id: str) -> None:
        self.memory.drop_session(session_id)

        if self.last_session_id == session_id:
            self.last_session_id = None

        logger.info(f"[会话] 已删除 {session_id}")

    def clear_sessions(self) -> None:
        self.memory.clear()
        self.last_session_id = None
        logger.info("[会话] 已清空全部")

    def _continue_response(
            self,
            response: ChatResponse,
            base_messages: list[ChatMessage],
            max_continuations: int = 2,
    ) -> ChatResponse:
        # 只续写因长度限制而截断、且没有工具调用的回复。
        if response.finish_reason != "length" or response.tool_calls:
            return response

        content_parts = [response.content]

        for attempt in range(1, max_continuations + 1):
            full_content = "".join(content_parts)

            continuation_messages = list(base_messages)

            # 把已生成的部分作为 assistant 上文，让模型从那里继续。
            if full_content:
                continuation_messages.append(ChatMessage(
                    role="assistant",
                    content=[{"type": "text", "text": full_content}],
                ))

            continuation_messages.append(ChatMessage(
                role="user",
                content=[{
                    "type": "text",
                    "text": (
                        "请从上次回复中断的位置继续。"
                        "不要重复已经写出的内容，只输出剩余部分。"
                    ),
                }],
            ))

            try:
                next_response = self.provider.invoke(
                    messages=continuation_messages,
                    tools=[],  # 续写阶段不开放工具，避免混入新的工具调用
                    enable_thinking=self.definition.enable_thinking,
                    temperature=self.definition.temperature,
                    max_tokens=self.definition.max_tokens,
                )
            except Exception as e:
                logger.error(f"[续写失败] 第 {attempt} 次续写请求失败：{e}")
                return ChatResponse(
                    content="".join(content_parts),
                    tool_calls=[],
                    finish_reason="continuation_error",
                    reasoning=response.reasoning,
                )

            # 续写请求没有提供工具定义；若 Provider 仍返回工具调用，停止续写。
            if next_response.tool_calls:
                logger.warning("[续写中止] 续写响应意外包含工具调用")
                return ChatResponse(
                    content="".join(content_parts),
                    tool_calls=[],
                    finish_reason="continuation_unexpected_tool_call",
                    reasoning=response.reasoning,
                )

            content_parts.append(next_response.content or "")
            logger.info(f"[续写] 已完成第 {attempt} 次，finish_reason={next_response.finish_reason}")

            if next_response.finish_reason != "length":
                return ChatResponse(
                    content="".join(content_parts),
                    tool_calls=[],
                    finish_reason=next_response.finish_reason,
                    reasoning=response.reasoning,
                )

        logger.warning(f"[续写停止] 已达到最多续写次数 {max_continuations}")
        return ChatResponse(
            content="".join(content_parts),
            tool_calls=[],
            finish_reason="length",
            reasoning=response.reasoning,
        )

    def run(self, message: ChatMessage, session_id: str | None = None, skill: str | None = None) -> ChatResponse:

        if session_id is None:
            session_id = uuid.uuid4().hex[:16]
            logger.info(f"[会话] 未指定 session_id，新建 {session_id}")
        self.last_session_id = session_id                  # ← 记下来给调用方用

        # 这次对话生效的技能：显式传了就用新的，没传就沿用会话里存的
        if skill is not None:
            if skill not in self.skills:
                logger.warning(f"[技能] '{skill}' 不存在，忽略")
                active_skill = self.memory.get_active_skill(session_id)   # 传错了，用旧的
            else:
                self.memory.set_active_skill(session_id, skill)
                active_skill = skill
        else:
            active_skill = self.memory.get_active_skill(session_id)       # 没传，查一次

        self.memory.add(session_id, message)

        # messages.append(message)

        tool_schemas = self._get_tool_schemas()

        for _ in range(1, self.max_turns + 1):
            messages = [self._system_message(active_skill)] + self.memory.get_messages(session_id)
            logger.info(f"[轮次] {_} / {self.max_turns}， 发出 {len(messages)} 条消息")

            response = self.provider.invoke(
                messages=messages,
                tools=tool_schemas,
                enable_thinking=self.definition.enable_thinking,
                temperature=self.definition.temperature,
                max_tokens=self.definition.max_tokens,
            )

            if response.tool_calls:
                # 工具调用消息必须先保存，后续 tool 消息才能和它配对。
                self.memory.add(session_id, ChatMessage(
                    role="assistant",
                    content=[{"type": "text", "text": response.content}] if response.content else [],
                    tool_calls=response.tool_calls,
                    token_usage=response.token_usage,
                ))

                for tool_call in response.tool_calls:
                    result = self._execute_tool(tool_call)
                    self.memory.add(session_id, ChatMessage(
                        role="tool",
                        content=[{"type": "text", "text": result}],
                        tool_call_id=tool_call.id,
                    ))
                continue

            # 没有工具调用时，先完成可能的续写。
            response = self._continue_response(response, messages)

            # 只保存最终合并后的 assistant 回复。
            self.memory.add(session_id, ChatMessage(
                role="assistant",
                content=[{"type": "text", "text": response.content}] if response.content else [],
                token_usage=response.token_usage,
            ))

            if response.finish_reason == "stop":
                logger.info(f"[完成] {_} 轮，正常结束")
            else:
                logger.warning(
                    f"[未确认完成] {_} 轮，finish_reason={response.finish_reason}"
                )

            return response
        logger.warning(f"[轮次] 达到上限 {self.max_turns}，强制结束")
        return ChatResponse(content="错误：达到最大迭代次数", tool_calls=[], finish_reason="max_turns")