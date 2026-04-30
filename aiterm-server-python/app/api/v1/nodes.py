from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.models import Response, Node, NodeCreate, NodeUpdate
from app.models.common import PaginatedResponse
from app.services import NodeService
from app.api.deps import get_node_service, get_current_user_optional

router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.get("")
async def list_nodes(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    service: NodeService = Depends(get_node_service)
):
    items, total = await service.list_nodes(page, page_size)
    paginated = PaginatedResponse.create(
        items=[node.model_dump() for node in items],
        total=total,
        page=page,
        page_size=page_size
    )
    return Response(data=paginated.model_dump())


@router.post("")
async def create_node(
    request: NodeCreate,
    service: NodeService = Depends(get_node_service)
):
    node = await service.create_node(request.name, request.host, request.port)
    return Response(data=node.model_dump())


@router.get("/{node_id}")
async def get_node(
    node_id: str,
    service: NodeService = Depends(get_node_service)
):
    node = await service.get_node(node_id)
    if not node:
        return Response(code=4042, message="node not found")
    return Response(data=node.model_dump())


@router.put("/{node_id}")
async def update_node(
    node_id: str,
    request: NodeUpdate,
    service: NodeService = Depends(get_node_service)
):
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    node = await service.update_node(node_id, **update_data)
    if not node:
        return Response(code=4042, message="node not found")
    return Response(data=node.model_dump())


@router.delete("/{node_id}")
async def delete_node(
    node_id: str,
    service: NodeService = Depends(get_node_service)
):
    success = await service.delete_node(node_id)
    if not success:
        return Response(code=4042, message="node not found or cannot be deleted")
    return Response(data={"node_id": node_id, "status": "deleted"})
