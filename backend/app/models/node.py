from pydantic import BaseModel
from typing import Optional

from .enums import NodeStatus


class Node(BaseModel):
    id: str
    name: str
    host: str
    port: int
    status: NodeStatus = NodeStatus.ONLINE
    node_type: str = "local"
    api_base_url: Optional[str] = None
    auth_username: Optional[str] = None
    encrypted_password: Optional[str] = None
    use_tls: bool = True
    is_connected: bool = False
    last_connected: Optional[str] = None


class NodeCreate(BaseModel):
    name: str
    host: str
    port: int
    node_type: str = "local"
    api_base_url: Optional[str] = None
    auth_username: Optional[str] = None
    password: Optional[str] = None  # plaintext, will be encrypted
    use_tls: bool = True


class NodeUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    status: Optional[NodeStatus] = None
    node_type: Optional[str] = None
    api_base_url: Optional[str] = None
    auth_username: Optional[str] = None
    password: Optional[str] = None
    use_tls: Optional[bool] = None
