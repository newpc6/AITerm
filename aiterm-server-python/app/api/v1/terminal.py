from fastapi import APIRouter, Depends
from datetime import datetime

from app.models import Response, TerminalExecuteRequest, TerminalExecuteResponse
from app.services import execute_command, NodeService
from app.api.deps import get_node_service
from app.utils import now_iso

router = APIRouter(prefix="/terminal", tags=["terminal"])


@router.post("/execute")
async def execute_terminal_command(
    request: TerminalExecuteRequest,
    node_service: NodeService = Depends(get_node_service)
):
    if not request.command:
        return Response(code=1001, message="command is required")

    node_id = request.node_id or "1"
    node_name = "local"

    node = await node_service.get_node(node_id)
    if node:
        node_name = node.name

    result = await execute_command(request.command)

    output = "\n".join(content for _, content in result.lines)

    return Response(
        data=TerminalExecuteResponse(
            command=request.command,
            output=output,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            node_id=node_id,
            node_name=node_name,
            timestamp=now_iso()
        ).model_dump()
    )
