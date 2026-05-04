from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, BigInteger, Enum
from datetime import datetime, timezone
import enum

from app.db.base import Base


class FileSource(str, enum.Enum):
    GENERATED = "generated"
    UPLOADED = "uploaded"
    SYSTEM = "system"


class FileModel(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size = Column(BigInteger, nullable=False, default=0)
    file_type = Column(String(100), nullable=True)
    mime_type = Column(String(100), nullable=True)
    source = Column(String(20), nullable=False, default="generated")
    chat_id = Column(Integer, nullable=True)
    message_id = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(
        timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        created_at_str = None
        if self.created_at:
            dt = self.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            created_at_str = dt.isoformat()

        updated_at_str = None
        if self.updated_at:
            dt = self.updated_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            updated_at_str = dt.isoformat()

        return {
            "id": str(self.id),
            "uuid": self.uuid,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "mime_type": self.mime_type,
            "source": self.source,
            "chat_id": str(self.chat_id) if self.chat_id else None,
            "message_id": str(self.message_id) if self.message_id else None,
            "description": self.description,
            "is_deleted": self.is_deleted,
            "created_at": created_at_str,
            "updated_at": updated_at_str
        }
