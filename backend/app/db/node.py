from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

from app.db.base import Base


class NodeModel(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False, default="online")

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "status": self.status
        }
