import json
from typing import List, Optional, Tuple
from sqlalchemy import select, update, func

from app.db import async_session_maker
from app.db.model_setting import ModelConfigModel
from app.models.model_setting import ModelConfig
from app.utils import now_iso


class ModelConfigRepository:
    async def list_models(self, page: int = 1, page_size: int = 20, user_id: int = None) -> Tuple[List[ModelConfig], int]:
        async with async_session_maker() as session:
            if user_id:
                count_query = select(func.count(ModelConfigModel.id)).where(
                    ModelConfigModel.user_id == user_id
                )
                items_query = select(ModelConfigModel).where(
                    ModelConfigModel.user_id == user_id
                )
            else:
                count_query = select(func.count(ModelConfigModel.id))
                items_query = select(ModelConfigModel)

            count_result = await session.execute(count_query)
            total = count_result.scalar() or 0

            offset = (page - 1) * page_size
            result = await session.execute(
                items_query
                .order_by(
                    ModelConfigModel.is_default.desc(),
                    ModelConfigModel.name
                )
                .offset(offset)
                .limit(page_size)
            )
            models = result.scalars().all()
            return [self._to_domain(m) for m in models], total

    async def get_model(self, model_id: str) -> Optional[ModelConfig]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ModelConfigModel).where(
                    ModelConfigModel.id == int(model_id))
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def get_default_model(self) -> Optional[ModelConfig]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ModelConfigModel).where(
                    ModelConfigModel.is_default == 1).limit(1)
            )
            model = result.scalar_one_or_none()
            return self._to_domain(model) if model else None

    async def create_model(self, model: ModelConfig) -> ModelConfig:
        async with async_session_maker() as session:
            now = now_iso()
            db_model = ModelConfigModel(
                name=model.name,
                api_type=model.api_type,
                api_url=model.api_url,
                api_key=model.api_key,
                model=model.model,
                temperature=int(model.temperature * 100),
                context_length=model.context_length,
                thinking_type=model.thinking_type,
                extra_params_json=json.dumps(model.extra_params),
                extra_body_json=json.dumps(model.extra_body),
                extra_headers_json=json.dumps(model.extra_headers),
                is_default=1 if model.is_default else 0,
                user_id=int(model.user_id) if model.user_id else None,
                scope=model.scope or "private",
                created_at=now,
                updated_at=now
            )
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return self._to_domain(db_model)

    async def update_model(self, model_id: str, model: ModelConfig) -> Optional[ModelConfig]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ModelConfigModel).where(
                    ModelConfigModel.id == int(model_id))
            )
            db_model = result.scalar_one_or_none()
            if not db_model:
                return None

            db_model.name = model.name
            db_model.api_type = model.api_type
            db_model.api_url = model.api_url
            db_model.api_key = model.api_key
            db_model.model = model.model
            db_model.temperature = int(model.temperature * 100)
            db_model.context_length = model.context_length
            db_model.thinking_type = model.thinking_type
            db_model.extra_params_json = json.dumps(model.extra_params)
            db_model.extra_body_json = json.dumps(model.extra_body)
            db_model.extra_headers_json = json.dumps(model.extra_headers)
            db_model.is_default = 1 if model.is_default else 0
            db_model.updated_at = now_iso()

            await session.commit()
            await session.refresh(db_model)
            return self._to_domain(db_model)

    async def delete_model(self, model_id: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                select(ModelConfigModel).where(
                    ModelConfigModel.id == int(model_id))
            )
            db_model = result.scalar_one_or_none()
            if not db_model:
                return False

            await session.delete(db_model)
            await session.commit()
            return True

    async def set_default_model(self, model_id: str) -> Optional[ModelConfig]:
        async with async_session_maker() as session:
            await session.execute(
                update(ModelConfigModel).values(is_default=0)
            )

            result = await session.execute(
                select(ModelConfigModel).where(
                    ModelConfigModel.id == int(model_id))
            )
            db_model = result.scalar_one_or_none()
            if not db_model:
                return None

            db_model.is_default = 1
            db_model.updated_at = now_iso()
            await session.commit()
            await session.refresh(db_model)
            return self._to_domain(db_model)

    def _to_domain(self, model: ModelConfigModel) -> Optional[ModelConfig]:
        if not model:
            return None
        extra_params = {}
        extra_body = {}
        extra_headers = {}
        try:
            extra_params = json.loads(
                model.extra_params_json) if model.extra_params_json else {}
        except:
            pass
        try:
            extra_body = json.loads(
                model.extra_body_json) if model.extra_body_json else {}
        except:
            pass
        try:
            extra_headers = json.loads(
                model.extra_headers_json) if model.extra_headers_json else {}
        except:
            pass

        return ModelConfig(
            id=str(model.id),
            name=model.name,
            api_type=model.api_type,
            api_url=model.api_url,
            api_key=model.api_key,
            model=model.model,
            temperature=model.temperature / 100.0,
            context_length=model.context_length,
            thinking_type=model.thinking_type,
            extra_params=extra_params,
            extra_body=extra_body,
            extra_headers=extra_headers,
            is_default=bool(model.is_default),
            user_id=str(model.user_id) if model.user_id else None,
            scope=model.scope or "private",
            team_id=str(model.team_id) if model.team_id else None,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
