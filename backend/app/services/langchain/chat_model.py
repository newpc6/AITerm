import logging
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from openai import AsyncOpenAI
from pydantic import ConfigDict

from app.models.model_setting import ModelConfig

logger = logging.getLogger("aiterm")


class AITermChatModel(BaseChatModel):
    model_setting: ModelConfig
    _client: Optional[AsyncOpenAI] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def _llm_type(self) -> str:
        return "aiterm-chat"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"model": self.model_setting.model, "api_url": self.model_setting.api_url}

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            headers = {}
            if self.model_setting.extra_headers:
                headers.update(self.model_setting.extra_headers)
            self._client = AsyncOpenAI(
                base_url=self.model_setting.api_url.rstrip("/"),
                api_key=self.model_setting.api_key or "EMPTY",
                timeout=90.0,
                default_headers=headers,
            )
        return self._client

    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        converted = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                converted.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                converted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                entry: Dict[str, Any] = {"role": "assistant"}
                if msg.content:
                    entry["content"] = msg.content
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    entry["tool_calls"] = msg.tool_calls
                converted.append(entry)
            elif isinstance(msg, ToolMessage):
                converted.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })
        return converted

    def _build_extra_body(self) -> Dict[str, Any]:
        extra_body = {}
        thinking_type = getattr(self.model_setting, 'thinking_type', 'default')
        if thinking_type == "enabled":
            extra_body["thinking"] = {"type": "enabled"}
        if self.model_setting.extra_body:
            extra_body.update(self.model_setting.extra_body)
        return extra_body

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise NotImplementedError("Synchronous generation is not supported, use async")

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        client = self._get_client()
        converted = self._convert_messages(messages)
        extra_body = self._build_extra_body()
        extra_params = self.model_setting.extra_params or {}

        tools = kwargs.get("tools")
        tool_choice = kwargs.get("tool_choice")

        params: Dict[str, Any] = {
            "model": self.model_setting.model,
            "messages": converted,
            "temperature": self.model_setting.temperature,
            "stream": False,
        }
        if extra_body:
            params["extra_body"] = extra_body
        if extra_params:
            params.update(extra_params)
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice or "auto"

        response = await client.chat.completions.create(**params)

        if not response.choices:
            raise ValueError("Model returned no response")

        choice = response.choices[0]
        msg = choice.message

        ai_message = AIMessage(content=msg.content or "")

        if msg.tool_calls:
            ai_message.tool_calls = [
                {
                    "id": tc.id,
                    "name": tc.function.name if tc.function else "",
                    "args": self._safe_json_parse(tc.function.arguments if tc.function else "{}"),
                    "type": "tool_call",
                }
                for tc in msg.tool_calls
            ]

        generation = ChatGeneration(message=ai_message)
        return ChatResult(generations=[generation])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        raise NotImplementedError("Use async streaming")

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        client = self._get_client()
        converted = self._convert_messages(messages)
        extra_body = self._build_extra_body()
        extra_params = self.model_setting.extra_params or {}

        tools = kwargs.get("tools")
        tool_choice = kwargs.get("tool_choice")

        params: Dict[str, Any] = {
            "model": self.model_setting.model,
            "messages": converted,
            "temperature": self.model_setting.temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if extra_body:
            params["extra_body"] = extra_body
        if extra_params:
            params.update(extra_params)
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice or "auto"

        stream = await client.chat.completions.create(**params)

        tool_call_data: Dict[int, Dict[str, Any]] = {}

        async for chunk in stream:
            if not chunk.choices:
                if chunk.usage and run_manager:
                    pass
                continue

            delta = chunk.choices[0].delta

            if delta.content:
                chunk_msg = AIMessageChunk(content=delta.content)
                if run_manager:
                    await run_manager.on_llm_new_token(delta.content, chunk=chunk_msg)
                yield ChatGenerationChunk(message=chunk_msg)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index or 0
                    if idx not in tool_call_data:
                        tool_call_data[idx] = {"id": tc.id, "function": {"name": "", "arguments": ""}}
                    if tc.function:
                        if tc.function.name:
                            tool_call_data[idx]["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_call_data[idx]["function"]["arguments"] += tc.function.arguments

    def _safe_json_parse(self, text: str) -> Dict[str, Any]:
        import json
        try:
            return json.loads(text or "{}")
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse tool arguments JSON: {text[:200]}")
            return {}


def create_chat_model(model_config: ModelConfig) -> AITermChatModel:
    return AITermChatModel(model_setting=model_config)
