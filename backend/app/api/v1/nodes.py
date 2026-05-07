from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List

from app.models import Response, Node, NodeCreate, NodeUpdate
from app.models.common import PaginatedResponse
from app.services import NodeService
from app.api.deps import get_node_service, get_current_user_optional, get_current_user
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import httpx

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
    node = await service.create_node(
        request.name, request.host, request.port,
        node_type=request.node_type, api_base_url=request.api_base_url,
        auth_username=request.auth_username, password=request.password,
        use_tls=request.use_tls,
    )
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
    update_data = {k: v for k, v in request.model_dump().items()
                   if v is not None}
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


@router.get("/{node_id}/health")
async def node_health(node_id: str, service: NodeService = Depends(get_node_service)):
    from app.services.remote_proxy import RemoteNodeProxy
    node = await service.get_node(node_id)
    if not node:
        raise HTTPException(404, "Node not found")
    proxy = RemoteNodeProxy(node)
    ok = await proxy.health_check()
    return Response(data={"node_id": node_id, "healthy": ok})


@router.post("/batch-chat")
async def batch_chat(payload: dict, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(401)
    message = payload.get("message", "")
    node_ids = payload.get("node_ids", [])
    if not message or not node_ids:
        raise HTTPException(400, "message and node_ids required")

    async def event_generator():
        from app.services.remote_proxy import RemoteNodeProxy
        from app.repositories import NodeRepository
        repo = NodeRepository()
        for nid in node_ids:
            node = await repo.get_node(nid)
            if not node:
                yield {"event": "node.error", "data": json.dumps({"node_id": nid, "error": "Node not found"})}
                continue
            yield {"event": "node.start", "data": json.dumps({"node_id": nid, "node_name": node.name})}
            try:
                proxy = RemoteNodeProxy(node)
                async for chunk in proxy.stream_chat({"message": message}):
                    yield {"event": "node.chunk", "data": json.dumps({"node_id": nid, "data": chunk.decode(errors='replace')})}
                yield {"event": "node.done", "data": json.dumps({"node_id": nid})}
            except Exception as e:
                yield {"event": "node.error", "data": json.dumps({"node_id": nid, "error": str(e)})}
                yield {"event": "node.done", "data": json.dumps({"node_id": nid, "error": str(e)})}

    return EventSourceResponse(event_generator())


@router.get("/{node_id}/scheduled-tasks")
async def remote_scheduled_tasks(node_id: str, service: NodeService = Depends(get_node_service)):
    from app.services.remote_proxy import RemoteNodeProxy
    node = await service.get_node(node_id)
    if not node:
        raise HTTPException(404, "Node not found")
    proxy = RemoteNodeProxy(node)
    token = await proxy.get_token()
    if not token:
        raise HTTPException(400, "Cannot authenticate to remote node")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{proxy.base_url}/api/v1/scheduler",
            headers={"Authorization": f"Bearer {token}"},
        )
        return Response(data=resp.json() if resp.status_code == 200 else [])
