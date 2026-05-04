import uuid
import os
from typing import List, Optional
from sqlalchemy import select, delete, func, or_

from app.db import async_session_maker
from app.db.file import FileModel, FileSource
from app.models.file import File, FileCreate


class FileRepository:
    async def list_files(
        self,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        file_type: Optional[str] = None,
        source: Optional[str] = None,
        include_deleted: bool = False
    ) -> tuple[List[File], int]:
        async with async_session_maker() as session:
            query = select(FileModel)
            count_query = select(func.count(FileModel.id))

            if not include_deleted:
                query = query.where(FileModel.is_deleted == False)
                count_query = count_query.where(FileModel.is_deleted == False)

            if search:
                search_filter = or_(
                    FileModel.filename.ilike(f"%{search}%"),
                    FileModel.original_filename.ilike(f"%{search}%"),
                    FileModel.description.ilike(f"%{search}%")
                )
                query = query.where(search_filter)
                count_query = count_query.where(search_filter)

            if file_type:
                query = query.where(FileModel.file_type == file_type)
                count_query = count_query.where(FileModel.file_type == file_type)

            if source:
                query = query.where(FileModel.source == source)
                count_query = count_query.where(FileModel.source == source)

            query = query.order_by(FileModel.created_at.desc())
            query = query.offset(skip).limit(limit)

            result = await session.execute(query)
            models = result.scalars().all()

            count_result = await session.execute(count_query)
            total = count_result.scalar() or 0

            return [self._to_domain(m) for m in models], total

    async def get_file(self, file_id: str) -> Optional[File]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(FileModel).where(FileModel.id == int(file_id))
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def get_file_by_uuid(self, file_uuid: str) -> Optional[File]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(FileModel).where(FileModel.uuid == file_uuid)
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def create_file(self, data: FileCreate) -> File:
        async with async_session_maker() as session:
            file_uuid = str(uuid.uuid4())
            model = FileModel(
                uuid=file_uuid,
                filename=data.filename,
                original_filename=data.original_filename,
                file_path=data.file_path,
                file_size=data.file_size,
                file_type=data.file_type,
                mime_type=data.mime_type,
                source=data.source,
                chat_id=int(data.chat_id) if data.chat_id else None,
                message_id=int(data.message_id) if data.message_id else None,
                description=data.description,
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def delete_file(self, file_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                select(FileModel).where(FileModel.id == int(file_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return False

            if os.path.exists(model.file_path):
                try:
                    os.remove(model.file_path)
                except Exception:
                    pass

            model.is_deleted = True
            await session.commit()
            return True

    async def delete_files(self, file_ids: List[str]) -> int:
        async with async_session_maker() as session:
            deleted_count = 0
            for file_id in file_ids:
                result = await session.execute(
                    select(FileModel).where(FileModel.id == int(file_id))
                )
                model = result.scalar_one_or_none()
                if model:
                    if os.path.exists(model.file_path):
                        try:
                            os.remove(model.file_path)
                        except Exception:
                            pass
                    model.is_deleted = True
                    deleted_count += 1
            await session.commit()
            return deleted_count

    async def hard_delete_file(self, file_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                delete(FileModel).where(FileModel.id == int(file_id))
            )
            await session.commit()
            return result.rowcount > 0

    def _to_domain(self, model: FileModel) -> File:
        return File(**model.to_dict())
