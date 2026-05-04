from pydantic import BaseModel


class TerminalExecuteRequest(BaseModel):
    command: str
    node_id: str = "1"


class TerminalExecuteResponse(BaseModel):
    command: str
    output: str
    exit_code: int
    timed_out: bool
    node_id: str
    node_name: str
    timestamp: str
