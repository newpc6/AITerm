from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class FileSource(str, Enum):
    GENERATED = "generated"
    UPLOADED = "uploaded"
    SYSTEM = "system"


class FileBase(BaseModel):
    filename: str
    original_filename: str
    file_path: str
    file_size: int = 0
    file_type: Optional[str] = None
    mime_type: Optional[str] = None
    source: str = "generated"
    chat_id: Optional[str] = None
    message_id: Optional[str] = None
    description: Optional[str] = None


class File(FileBase):
    id: str
    uuid: str
    is_deleted: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class FileCreate(FileBase):
    pass


class FileResponse(BaseModel):
    id: str
    uuid: str
    filename: str
    original_filename: str
    file_size: int
    file_type: Optional[str] = None
    mime_type: Optional[str] = None
    source: str = "generated"
    chat_id: Optional[str] = None
    message_id: Optional[str] = None
    description: Optional[str] = None
    is_deleted: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    files: List[FileResponse]
    total: int


class FileBatchDelete(BaseModel):
    ids: List[str]
