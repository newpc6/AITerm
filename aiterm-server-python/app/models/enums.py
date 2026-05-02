from enum import Enum


class NodeStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ConversationMode(str, Enum):
    CHAT = "chat"
    EXECUTE = "execute"
