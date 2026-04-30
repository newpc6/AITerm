from typing import List, Optional, Tuple
from datetime import datetime

from app.models import Node, NodeStatus
from app.repositories import INodeRepository
from app.services.command import describe_node


class NodeService:
    def __init__(self, repo: INodeRepository):
        self.repo = repo

    async def list_nodes(self, page: int = 1, page_size: int = 20) -> Tuple[List[Node], int]:
        nodes, total = await self.repo.list_nodes(page, page_size)
        if not nodes and page == 1:
            local_node = Node(
                id="1",
                name="local",
                host="127.0.0.1",
                port=22,
                status=NodeStatus.ONLINE
            )
            await self.repo.create_node(local_node)
            return [local_node], 1
        return nodes, total

    async def get_node(self, node_id: str) -> Optional[Node]:
        return await self.repo.get_node(node_id)

    async def create_node(self, name: str, host: str, port: int) -> Node:
        node = Node(
            id="0",
            name=name,
            host=host,
            port=port,
            status=NodeStatus.ONLINE
        )
        return await self.repo.create_node(node)

    async def update_node(self, node_id: str, **kwargs) -> Optional[Node]:
        node = await self.repo.get_node(node_id)
        if not node:
            return None
        for key, value in kwargs.items():
            if hasattr(node, key) and value is not None:
                setattr(node, key, value)
        return await self.repo.update_node(node_id, node)

    async def delete_node(self, node_id: str) -> bool:
        if node_id == "1":
            return False
        return await self.repo.delete_node(node_id)
