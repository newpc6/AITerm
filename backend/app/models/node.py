from pydantic import BaseModel
from typing import Optional

from .enums import NodeStatus


class Node(BaseModel):
    id: str
    name: str
    host: str
    port: int
    status: NodeStatus = NodeStatus.ONLINE


class NodeCreate(BaseModel):
    name: str
    host: str
    port: int


class NodeUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    status: Optional[NodeStatus] = None
