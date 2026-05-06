import json
import logging
import httpx
from typing import AsyncGenerator, Dict, Any, List, Optional

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

    def _get_headers(self) -> Dict[str, str]:
        headers = super()._get_headers()
        headers["Accept"] = "application/json, text/event-stream"
        return headers

    def _build_payload(self, messages: List[Dict[str, Any]],
                       tools: Optional[List[Dict[str, Any]]] = None,
                       stream: bool = True,
                       temperature: Optional[float] = None) -> Dict[str, Any]:
        thinking_type = getattr(self.config, 'thinking_type', 'default')
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature or 0.7,
            "stream": stream,
        }

        if thinking_type == "enabled":
            payload["thinking"] = {"type": "enabled"}
            payload["reasoning_effort"] = "high"

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        if self.extra_params:
            payload.update(self.extra_params)

        if self.extra_body:
            for k, v in self.extra_body.items():
                if k not in payload:
                    payload[k] = v

        return payload

    def _parse_stream_chunk(self, data: dict) -> Dict[str, Any]:
        result = {}
        if data.get("usage"):
            result["usage"] = data["usage"]

        if "choices" in data and len(data["choices"]) > 0:
            delta = data["choices"][0].get("delta", {})

            if delta.get("reasoning_content"):
                result["type"] = "reasoning"
                result["delta"] = delta["reasoning_content"]
                return result

            if delta.get("content"):
                result["type"] = "content"
                result["delta"] = delta["content"]
                return result

            if delta.get("tool_calls"):
                result["tool_calls"] = delta["tool_calls"]
                result["type"] = "tool_calls"

        return result

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        stream: bool = True
    ) -> str:
        if not self.api_url or not self.model:
            raise ValueError("LLM setting incomplete")

        payload = self._build_payload(messages, stream=False, temperature=temperature)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._get_chat_url(),
                headers=self._get_headers(),
                json=payload
            )

            if response.status_code >= 400:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    pass
                if "error" in error_data and error_data["error"].get("message"):
                    raise ValueError(error_data["error"]["message"])
                raise ValueError(f"Model request failed: HTTP {response.status_code}")

            data = response.json()
            if "choices" not in data or len(data["choices"]) == 0:
                raise ValueError("Model returned no valid response")
            content = data["choices"][0].get("message", {}).get("content", "")
            if isinstance(content, list):
                content = "\n".join(
                    item.get("text", "") for item in content
                    if isinstance(item, dict) and "text" in item
                )
            if not content.strip():
                raise ValueError("Model returned empty content")
            return content.strip()

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.api_url or not self.model:
            raise ValueError("LLM setting incomplete")

        payload = self._build_payload(messages, stream=True, temperature=temperature)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                self._get_chat_url(),
                headers=self._get_headers(),
                json=payload
            ) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    try:
                        error_data = json.loads(body)
                        if "error" in error_data and error_data["error"].get("message"):
                            raise ValueError(error_data["error"]["message"])
                    except json.JSONDecodeError:
                        pass
                    raise ValueError(f"Model request failed: HTTP {response.status_code}")

                usage = {}
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    parsed = self._parse_stream_chunk(data)
                    if parsed.get("type") == "reasoning":
                        yield {"type": "reasoning", "content": parsed["delta"], "reasoning_done": False}
                    elif parsed.get("type") == "content":
                        yield {"type": "content", "content": parsed["delta"], "reasoning_done": True}
                    elif parsed.get("usage"):
                        usage = parsed["usage"]

                if usage:
                    yield {"type": "usage", "usage": usage}

    async def chat_with_tools_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: Optional[float] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.api_url or not self.model:
            raise ValueError("LLM setting incomplete")

        payload = self._build_payload(messages, tools=tools, stream=True, temperature=temperature)

        for tool in tools:
            if "function" in tool and "parameters" in tool["function"]:
                params = tool["function"]["parameters"]
                if "required" in params and params["required"] is None:
                    params["required"] = []
                if "properties" in params and params["properties"]:
                    for prop_name, prop in params["properties"].items():
                        if isinstance(prop, dict):
                            if "enum" in prop and prop["enum"] is None:
                                del prop["enum"]
                            if "default" in prop and prop["default"] is None:
                                del prop["default"]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                self._get_chat_url(),
                headers=self._get_headers(),
                json=payload
            ) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    try:
                        error_data = json.loads(body)
                        if "error" in error_data and error_data["error"].get("message"):
                            raise ValueError(error_data["error"]["message"])
                    except json.JSONDecodeError:
                        pass
                    raise ValueError(f"Model request failed: HTTP {response.status_code}")

                full_content = ""
                full_reasoning = ""
                tool_calls_data = {}
                usage_data = {}

                async for line in response.aiter_lines():
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        if data.get("usage"):
                            usage_data = data["usage"]

                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})

                            if delta.get("reasoning_content"):
                                chunk = delta["reasoning_content"]
                                full_reasoning += chunk
                                yield {"type": "reasoning", "delta": chunk}

                            if delta.get("content"):
                                chunk = delta["content"]
                                full_content += chunk
                                yield {"type": "content", "delta": chunk}

                            if delta.get("tool_calls"):
                                for tc in delta["tool_calls"]:
                                    idx = tc.get("index", 0)
                                    if idx not in tool_calls_data:
                                        tool_calls_data[idx] = {
                                            "id": "",
                                            "name": "",
                                            "arguments": ""
                                        }
                                    if tc.get("id"):
                                        tool_calls_data[idx]["id"] = tc["id"]
                                    if tc.get("function"):
                                        if tc["function"].get("name"):
                                            tool_calls_data[idx]["name"] = tc["function"]["name"]
                                        if tc["function"].get("arguments"):
                                            tool_calls_data[idx]["arguments"] += tc["function"]["arguments"]

                tool_calls_list = list(tool_calls_data.values()) if tool_calls_data else None

                yield {
                    "type": "done",
                    "content": full_content,
                    "reasoning_content": full_reasoning,
                    "tool_calls": tool_calls_list,
                    "usage": usage_data
                }
