import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse as FastAPIFileResponse

from app.models.common import Response, PaginatedResponse
from app.models.file import (
    FileResponse,
    FileListResponse,
    FileBatchDelete
)
from app.services.file_service import FileService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["files"])
file_service = FileService()


@router.get("", response_model=Response[FileListResponse])
async def list_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    file_type: Optional[str] = None,
    source: Optional[str] = None
):
    result = await file_service.list_files(
        page=page,
        page_size=page_size,
        search=search,
        file_type=file_type,
        source=source
    )
    return Response(data=result)


@router.get("/{file_id}", response_model=Response[FileResponse])
async def get_file(file_id: str):
    file = await file_service.get_file(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return Response(data=FileResponse(**file.model_dump()))


@router.get("/download/{file_uuid}")
async def download_file(file_uuid: str):
    download_info = await file_service.get_download_info(file_uuid)
    if not download_info:
        raise HTTPException(
            status_code=404, detail="File not found or has been deleted")

    return FastAPIFileResponse(
        path=download_info["file_path"],
        filename=download_info["filename"],
        media_type=download_info["mime_type"]
    )


@router.post("/upload", response_model=Response[FileResponse])
async def upload_file(
    file: UploadFile = File(...),
    chat_id: Optional[str] = None,
    message_id: Optional[str] = None,
    description: Optional[str] = None
):
    import os
    import uuid

    upload_dir = os.path.join(os.getcwd(), "uploads")
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir, exist_ok=True)

    file_uuid = str(uuid.uuid4())
    original_filename = file.filename or "unknown"
    safe_filename = original_filename.replace(
        "..", "").replace("/", "_").replace("\\", "_")
    stored_filename = f"{file_uuid[:8]}_{safe_filename}"
    file_path = os.path.join(upload_dir, stored_filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    registered_file = await file_service.register_file(
        file_path=file_path,
        original_filename=original_filename,
        chat_id=chat_id,
        message_id=message_id,
        description=description,
        source="uploaded"
    )

    return Response(data=FileResponse(**registered_file.model_dump()))


@router.delete("/{file_id}", response_model=Response[bool])
async def delete_file(file_id: str):
    success = await file_service.delete_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    return Response(data=success)


@router.post("/batch-delete", response_model=Response[int])
async def batch_delete_files(payload: FileBatchDelete):
    count = await file_service.delete_files(payload.ids)
    return Response(data=count, message=f"成功删除 {count} 个文件")


@router.get("/types/list", response_model=Response[list])
async def list_file_types():
    result = await file_service.list_files(page=1, page_size=1000)
    types = set()
    for f in result.files:
        if f.file_type:
            types.add(f.file_type)
    return Response(data=sorted(list(types)))


@router.get("/sources/list", response_model=Response[list])
async def list_file_sources():
    return Response(data=["generated", "uploaded", "system"])
