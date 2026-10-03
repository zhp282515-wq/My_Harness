from typing import Any

from myharness.providers.base import BaseProvider, ChatMessage
from myharness.providers.base import ChatResponse
import json
import httpx
from myharness.providers.base import ToolCall
from utils.logger_tool import logger
import time
import os


def _to_api_message(message: ChatMessage) -> dict[str, Any]:

    result: dict[str, Any] = {
        "role": message.role,
        "content": message.content,
    }

    if message.tool_calls:
        tool_calls = []
        for tool_call in message.tool_calls:
            tool_calls.append({
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": json.dumps(tool_call.arguments),
                },
            })
        result["tool_calls"] = tool_calls

    if message.tool_call_id:
        result["tool_call_id"] = message.tool_call_id

    return result


class DashScopeProvider(BaseProvider):
    def __init__(
            self,
            model: str,
            api_key: str | None = None,
            base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ):
        self.model = model
        key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not key:
            logger.error("[配置] 未找到 DASHSCOPE_API_KEY")
            raise ValueError("缺少 API Key：请设置环境变量 DASHSCOPE_API_KEY 或在 .env 中配置")
        self.api_key = key
        self.base_url = base_url.rstrip("/")

    def invoke(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        enable_thinking: bool = True,
        temperature: float = 0.7,
        timeout: float = 90,
        max_tokens: int = 4096,
    ) -> ChatResponse:

        tools = tools if tools is not None else []

        logger.info(f"[请求] {len(messages)} 条消息, {len(tools)} 个工具")

        payload = {
            "model": self.model,
            "messages": [_to_api_message(m) for m in messages],
            "enable_thinking": enable_thinking,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        logger.debug(f"[配置] model={self.model} thinking={enable_thinking} temp={temperature}")

        start = time.perf_counter()
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers = {"Authorization": f"Bearer {self.api_key}"},
            json = payload,
            timeout = timeout,
        )
        elapsed = time.perf_counter() - start
        logger.info(f"[响应] {resp.status_code}, 耗时 {elapsed:.2f}s")

        if resp.status_code != 200:
            logger.error(f"[错误] HTTP {resp.status_code}: {resp.text[:300]}")
            raise RuntimeError(f"DashScope 返回 {resp.status_code}: {resp.text[:300]}")

        try:
            data = resp.json()
        except Exception as e:
            logger.error(f"[解析] 响应不是合法 JSON: {e} | 原文: {resp.text[:300]}")
            raise RuntimeError(f"DashScope 响应无法解析为 JSON: {e}") from e
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            logger.error(f"[解析] 响应缺少 choices 或为空: {json.dumps(data, ensure_ascii=False)[:300]}")
            raise RuntimeError(f"DashScope 响应结构异常：choices 缺失或为空")

        choice = choices[0]
        msg = choice.get("message")
        if not isinstance(msg, dict):
            logger.error(f"[解析] choice 里没有 message: {json.dumps(choice, ensure_ascii=False)[:300]}")
            raise RuntimeError("DashScope 响应结构异常：缺少 message")

        tool_calls = []
        for c in msg.get("tool_calls") or []:
            raw_args = c["function"]["arguments"]
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError as e:
                logger.warning(f"[解析] {c['function']['name']} 的参数不是合法 JSON: {e}")
                logger.warning(f"[解析] 原文: {raw_args[:200]}")
                args = {}  # ← 兜底成空参数

            tool_calls.append(
                ToolCall(
                    id=c["id"],
                    name=c["function"]["name"],
                    arguments=args,
                )
            )

        token = data.get("usage")

        logger.info(f"[模型] finish_reason={choice.get('finish_reason', '')}, 工具调用 {len(tool_calls)} 个")
        for c in tool_calls:
            logger.info(f"  → {c.name}({c.arguments})")

        return ChatResponse(
            content=msg.get("content") or "",
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", ""),
            reasoning=msg.get("reasoning_content"),
            token_usage=token,
        )

    def stream(self):
        pass