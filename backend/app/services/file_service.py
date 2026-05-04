import os
import uuid
import mimetypes
from typing import List, Optional
from datetime import datetime

from app.repositories.file import FileRepository
from app.models.file import (
    File,
    FileCreate,
    FileResponse,
    FileListResponse,
    FileBatchDelete,
    FileSource
)


class FileService:
    def __init__(self):
        self.repository = FileRepository()

    async def list_files(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        file_type: Optional[str] = None,
        source: Optional[str] = None
    ) -> FileListResponse:
        skip = (page - 1) * page_size
        files, total = await self.repository.list_files(
            skip=skip,
            limit=page_size,
            search=search,
            file_type=file_type,
            source=source
        )
        return FileListResponse(
            files=[FileResponse(**f.model_dump()) for f in files],
            total=total
        )

    async def get_file(self, file_id: str) -> Optional[File]:
        return await self.repository.get_file(file_id)

    async def get_file_by_uuid(self, file_uuid: str) -> Optional[File]:
        return await self.repository.get_file_by_uuid(file_uuid)

    async def register_file(
        self,
        file_path: str,
        original_filename: Optional[str] = None,
        chat_id: Optional[str] = None,
        message_id: Optional[str] = None,
        description: Optional[str] = None,
        source: str = "generated"
    ) -> File:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_stat = os.stat(file_path)
        file_size = file_stat.st_size

        if original_filename is None:
            original_filename = os.path.basename(file_path)

        filename = f"{uuid.uuid4().hex[:8]}_{original_filename}"

        _, ext = os.path.splitext(original_filename)
        file_type = ext.lstrip('.').lower() if ext else None

        mime_type, _ = mimetypes.guess_type(original_filename)
        if mime_type is None:
            mime_type = 'application/octet-stream'

        data = FileCreate(
            filename=filename,
            original_filename=original_filename,
            file_path=file_path,
            file_size=file_size,
            file_type=file_type,
            mime_type=mime_type,
            source=source,
            chat_id=chat_id,
            message_id=message_id,
            description=description
        )

        return await self.repository.create_file(data)

    async def delete_file(self, file_id: str) -> bool:
        return await self.repository.delete_file(file_id)

    async def delete_files(self, file_ids: List[str]) -> int:
        return await self.repository.delete_files(file_ids)

    async def get_download_info(self, file_uuid: str) -> Optional[dict]:
        file = await self.repository.get_file_by_uuid(file_uuid)
        if not file or file.is_deleted:
            return None

        if not os.path.exists(file.file_path):
            return None

        return {
            "file_path": file.file_path,
            "filename": file.original_filename,
            "mime_type": file.mime_type,
            "file_size": file.file_size
        }

    def format_file_size(self, size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
