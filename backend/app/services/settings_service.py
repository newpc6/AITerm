from typing import List, Optional, Tuple
from datetime import datetime

from app.models import ModelConfig, ModelConfigCreate, ModelConfigUpdate
from app.repositories import IModelConfigRepository
from app.utils import now_iso


class ModelConfigService:
    def __init__(self, repo: IModelConfigRepository):
        self.repo = repo

    async def list_models(self, page: int = 1, page_size: int = 20) -> Tuple[List[ModelConfig], int]:
        return await self.repo.list_models(page, page_size)

    async def get_model(self, model_id: str) -> Optional[ModelConfig]:
        return await self.repo.get_model(model_id)

    async def get_default_model(self) -> Optional[ModelConfig]:
        return await self.repo.get_default_model()

    async def create_model(self, data: ModelConfigCreate) -> ModelConfig:
        now = now_iso()
        model = ModelConfig(
            id="0",
            name=data.name,
            api_url=data.api_url,
            api_key=data.api_key,
            model=data.model,
            temperature=data.temperature,
            extra_params=data.extra_params or {},
            extra_body=data.extra_body or {},
            extra_headers=data.extra_headers or {},
            is_default=data.is_default,
            created_at=now,
            updated_at=now
        )
        created = await self.repo.create_model(model)
        if data.is_default:
            await self.repo.set_default_model(created.id)
        return created

    async def update_model(self, model_id: str, data: ModelConfigUpdate) -> Optional[ModelConfig]:
        model = await self.repo.get_model(model_id)
        if not model:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(model, key, value)

        model.updated_at = now_iso()
        updated = await self.repo.update_model(model_id, model)

        if data.is_default:
            await self.repo.set_default_model(model_id)

        return updated

    async def delete_model(self, model_id: str) -> bool:
        model = await self.repo.get_model(model_id)
        if model and model.is_default:
            models, _ = await self.repo.list_models()
            if len(models) <= 1:
                raise ValueError("不能删除唯一的模型配置")
        return await self.repo.delete_model(model_id)

    async def set_default_model(self, model_id: str) -> bool:
        model = await self.repo.get_model(model_id)
        if not model:
            return False
        return await self.repo.set_default_model(model_id)


class GlobalSettingsService:
    def __init__(self, repo):
        self.repo = repo

    async def get_settings(self):
        return await self.repo.get_settings()

    async def save_settings(self, settings):
        return await self.repo.update_settings(settings)
