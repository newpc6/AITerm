import json
from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import INodeRepository
from app.models import Node, NodeStatus
from app.db import async_session_maker
from app.db.node import NodeModel


class NodeRepository(INodeRepository):
    async def list_nodes(self, page: int = 1, page_size: int = 20) -> Tuple[List[Node], int]:
        async with async_session_maker() as session:
            count_result = await session.execute(
                select(func.count(NodeModel.id))
            )
            total = count_result.scalar() or 0

            offset = (page - 1) * page_size
            result = await session.execute(
                select(NodeModel)
                .offset(offset)
                .limit(page_size)
            )
            models = result.scalars().all()
            return [self._to_domain(m) for m in models], total

    async def get_node(self, node_id: str) -> Optional[Node]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(NodeModel).where(NodeModel.id == int(node_id))
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def create_node(self, node: Node) -> Node:
        async with async_session_maker() as session:
            model = NodeModel(
                name=node.name,
                host=node.host,
                port=node.port,
                status=node.status.value if isinstance(node.status, NodeStatus) else node.status
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def update_node(self, node_id: str, node: Node) -> Optional[Node]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(NodeModel).where(NodeModel.id == int(node_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return None
            
            model.name = node.name
            model.host = node.host
            model.port = node.port
            if node.status:
                model.status = node.status.value if isinstance(node.status, NodeStatus) else node.status
            
            await session.commit()
            return self._to_domain(model)

    async def delete_node(self, node_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                delete(NodeModel).where(NodeModel.id == int(node_id))
            )
            await session.commit()
            return result.rowcount > 0

    def _to_domain(self, model: NodeModel) -> Node:
        return Node(
            id=str(model.id),
            name=model.name,
            host=model.host,
            port=model.port,
            status=NodeStatus(model.status) if model.status else NodeStatus.ONLINE
        )
