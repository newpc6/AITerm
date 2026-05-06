from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, List, Optional


class BaseLLMProvider(ABC):

    def __init__(self, config):
        self.config = config
        self.timeout = 90.0

    @property
    @abstractmethod
    def api_url(self) -> str:
        pass

    @property
    def api_key(self) -> str:
        return self.config.api_key

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def temperature(self) -> float:
        return self.config.temperature

    @property
    def extra_params(self) -> Dict[str, Any]:
        if hasattr(self.config, 'extra_params'):
            return self.config.extra_params or {}
        return {}

    @property
    def extra_body(self) -> Dict[str, Any]:
        if hasattr(self.config, 'extra_body'):
            return self.config.extra_body or {}
        return {}

    @property
    def extra_headers(self) -> Dict[str, str]:
        if hasattr(self.config, 'extra_headers'):
            return self.config.extra_headers or {}
        return {}

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.extra_headers:
            headers.update(self.extra_headers)
        return headers

    @abstractmethod
    def _get_chat_url(self) -> str:
        pass

    @abstractmethod
    def _build_payload(self, messages: List[Dict[str, Any]],
                       tools: Optional[List[Dict[str, Any]]] = None,
                       stream: bool = True,
                       temperature: Optional[float] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def _parse_stream_chunk(self, data: dict) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        stream: bool = True
    ) -> str:
        pass

    @abstractmethod
    async def chat_with_tools_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: Optional[float] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        pass
