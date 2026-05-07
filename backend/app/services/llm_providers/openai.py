import logging
from typing import AsyncGenerator, Dict, Any, List, Optional

from openai import AsyncOpenAI

from app.services.llm_providers.base import BaseLLMProvider

logger = logging.getLogger("aiterm")


class OpenAIProvider(BaseLLMProvider):

    @property
    def api_url(self) -> str:
        return self.config.api_url

    def _get_chat_url(self) -> str:
        url = self.config.api_url.rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        return f"{url}/chat/completions"

    def _get_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(
            base_url=self.config.api_url.rstrip("/"),
            api_key=self.config.api_key or "EMPTY",
            timeout=self.timeout,
            default_headers=self._get_headers_dict(),
        )

    def _get_headers_dict(self) -> Dict[str, str]:
        headers = {}
        if hasattr(self.config, 'extra_headers') and self.config.extra_headers:
            headers.update(self.config.extra_headers)
        return headers

    def _build_extra_body(self, tools=None) -> Dict[str, Any]:
        extra_body = {}

        thinking_type = getattr(self.config, 'thinking_type', 'default')
        if thinking_type == "enabled":
            extra_body["thinking"] = {"type": "enabled"}

        if hasattr(self.config, 'extra_body') and self.config.extra_body:
            extra_body.update(self.config.extra_body)

        return extra_body

    def _build_extra_params(self) -> Dict[str, Any]:
        extra_params = {}
        if hasattr(self.config, 'extra_params') and self.config.extra_params:
            extra_params.update(self.config.extra_params)
        return extra_params

    def _clean_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cleaned = []
        for tool in tools:
            t = {
                "type": tool.get("type", "function"),
                "function": dict(tool.get("function", {}))
            }
            if "parameters" in t["function"]:
                params = dict(t["function"]["parameters"])
                if "required" not in params or params["required"] is None:
                    params["required"] = []
                if "properties" in params and params["properties"]:
                    for prop_name, prop in params["properties"].items():
                        if isinstance(prop, dict):
                            if "enum" in prop and prop["enum"] is None:
                                del prop["enum"]
                            if "default" in prop and prop["default"] is None:
                                del prop["default"]
                t["function"]["parameters"] = params
            cleaned.append(t)
        return cleaned

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        stream: bool = True
    ) -> str:
        if not self.config.api_url or not self.config.model:
            raise ValueError("LLM setting incomplete")

        client = self._get_client()
        extra_body = self._build_extra_body()
        extra_params = self._build_extra_params()

        try:
            response = await client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=temperature or self.config.temperature or 0.7,
                stream=False,
                extra_body=extra_body if extra_body else None,
                **extra_params
            )
            if not response.choices:
                raise ValueError("Model returned no valid response")
            content = response.choices[0].message.content or ""
            if not content.strip():
                raise ValueError("Model returned empty content")
            return content.strip()
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise ValueError(str(e))

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.config.api_url or not self.config.model:
            raise ValueError("LLM setting incomplete")

        client = self._get_client()
        extra_body = self._build_extra_body()
        extra_params = self._build_extra_params()

        try:
            stream = await client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=temperature or self.config.temperature or 0.7,
                stream=True,
                extra_body=extra_body if extra_body else None,
                **extra_params
            )

            usage = {}
            async for chunk in stream:
                if self.debug_logging:
                    logger.debug(
                        f"Stream chunk: {chunk.model_dump_json(exclude_none=True)}")

                if chunk.usage:
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens or 0,
                        "completion_tokens": chunk.usage.completion_tokens or 0,
                        "total_tokens": chunk.usage.total_tokens or 0,
                    }

                if chunk.choices:
                    delta = chunk.choices[0].delta

                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        yield {"type": "reasoning", "content": delta.reasoning_content, "reasoning_done": False}
                        continue

                    if delta.content:
                        yield {"type": "content", "content": delta.content, "reasoning_done": True}

            if usage:
                yield {"type": "usage", "usage": usage}

        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            raise ValueError(str(e))

    async def chat_with_tools_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: Optional[float] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.config.api_url or not self.config.model:
            raise ValueError("LLM setting incomplete")

        client = self._get_client()
        cleaned_tools = self._clean_tools(tools)
        extra_body = self._build_extra_body()
        extra_params = self._build_extra_params()

        try:
            extra = {}
            if extra_body:
                extra["extra_body"] = extra_body
            extra.update(extra_params)

            stream = await client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=temperature or self.config.temperature or 0.7,
                stream=True,
                tools=cleaned_tools,
                tool_choice="auto",
                **extra
            )

            full_content = ""
            full_reasoning = ""
            tool_calls_data: Dict[int, dict] = {}
            usage_data = {}

            async for chunk in stream:
                if self.debug_logging:
                    logger.debug(
                        f"Tool stream chunk: {chunk.model_dump_json(exclude_none=True)}")

                if chunk.usage:
                    usage_data = {
                        "prompt_tokens": chunk.usage.prompt_tokens or 0,
                        "completion_tokens": chunk.usage.completion_tokens or 0,
                        "total_tokens": chunk.usage.total_tokens or 0,
                    }

                if chunk.choices:
                    delta = chunk.choices[0].delta

                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        chunk_text = delta.reasoning_content
                        full_reasoning += chunk_text
                        yield {"type": "reasoning", "delta": chunk_text}

                    if delta.content:
                        chunk_text = delta.content
                        full_content += chunk_text
                        yield {"type": "content", "delta": chunk_text}

                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index or 0
                            if idx not in tool_calls_data:
                                tool_calls_data[idx] = {
                                    "id": tc.id or "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""}
                                }
                            if tc.id:
                                tool_calls_data[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    tool_calls_data[idx]["function"]["name"] += tc.function.name
                                if tc.function.arguments:
                                    tool_calls_data[idx]["function"]["arguments"] += tc.function.arguments

                if chunk.choices and chunk.choices[0].finish_reason == "tool_calls":
                    tool_calls = [
                        tool_calls_data[i]
                        for i in sorted(tool_calls_data.keys())
                    ]
                    yield {
                        "type": "done",
                        "tool_calls": tool_calls,
                        "content": full_content,
                        "usage": usage_data,
                    }

            if usage_data:
                yield {"type": "usage", "usage": usage_data}

        except Exception as e:
            logger.error(f"Chat with tools stream error: {e}")
            raise ValueError(str(e))
