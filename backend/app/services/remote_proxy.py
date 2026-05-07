import logging
from typing import AsyncIterator

import httpx

from app.models import Node
from app.services.crypto_service import CryptoService

logger = logging.getLogger(__name__)


class RemoteNodeProxy:
    def __init__(self, node: Node):
        self.node = node
        self.base_url = (node.api_base_url or "").rstrip('/')
        self._crypto = CryptoService.get_instance()
        self._password = None
        if node.encrypted_password:
            self._password = self._crypto.decrypt(node.encrypted_password)

    async def get_token(self) -> str | None:
        if not self.base_url or not self.node.auth_username or not self._password:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.base_url}/api/v1/auth/login",
                    json={"username": self.node.auth_username, "password": self._password},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data", {}).get("access_token")
        except Exception as e:
            logger.error(f"Failed to get token for node {self.node.name}: {e}")
        return None

    async def health_check(self) -> bool:
        if not self.base_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/v1/health")
                return resp.status_code == 200
        except Exception:
            return False

    async def stream_chat(self, payload: dict) -> AsyncIterator[bytes]:
        token = await self.get_token()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/v1/chats/stream",
                json=payload,
                headers=headers,
            ) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk
