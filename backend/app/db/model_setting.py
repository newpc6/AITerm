from sqlalchemy import Column, Integer, String, Text, ForeignKey
from app.db.base import Base


class ModelConfigModel(Base):
    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    api_type = Column(String(50), nullable=False, default="openai")
    api_url = Column(String(500), nullable=False)
    api_key = Column(String(500), nullable=False, default="")
    model = Column(String(255), nullable=False)
    temperature = Column(Integer, nullable=False, default=70)
    context_length = Column(Integer, nullable=True)
    thinking_type = Column(String(50), nullable=False, default="default")
    extra_params_json = Column(Text, nullable=False, default="{}")
    extra_body_json = Column(Text, nullable=False, default="{}")
    extra_headers_json = Column(Text, nullable=False, default="{}")
    is_default = Column(Integer, nullable=False, default=0)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    scope = Column(String(20), nullable=False, default="private")
    team_id = Column(Integer, nullable=True)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "api_type": self.api_type,
            "api_url": self.api_url,
            "api_key": self.api_key,
            "model": self.model,
            "temperature": self.temperature / 100.0,
            "context_length": self.context_length,
            "thinking_type": self.thinking_type,
            "extra_params_json": self.extra_params_json,
            "extra_body_json": self.extra_body_json,
            "extra_headers_json": self.extra_headers_json,
            "is_default": bool(self.is_default),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
