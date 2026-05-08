import json
import logging
from typing import List, Optional

from sqlalchemy import select, delete, and_

from app.db import async_session_maker
from app.db.skill import SkillTemplateModel, UserSkillModel
from app.models.skill import SkillTemplate
from app.utils import now_iso

logger = logging.getLogger(__name__)


class SkillRepository:

    async def list_visible(self, user_id: int, scope: str = None) -> List[SkillTemplate]:
        async with async_session_maker() as session:
            if scope == "my":
                subq = select(UserSkillModel.template_id).where(UserSkillModel.user_id == user_id)
                query = select(SkillTemplateModel).where(
                    (SkillTemplateModel.user_id == user_id) | (SkillTemplateModel.id.in_(subq))
                )
            elif scope == "installed":
                subq = select(UserSkillModel.template_id).where(UserSkillModel.user_id == user_id)
                query = select(SkillTemplateModel).where(SkillTemplateModel.id.in_(subq))
            elif scope == "public":
                query = select(SkillTemplateModel).where(
                    and_(SkillTemplateModel.is_public == True, SkillTemplateModel.status == "approved")
                )
            elif scope == "pending":
                query = select(SkillTemplateModel).where(SkillTemplateModel.status == "pending")
            else:
                query = select(SkillTemplateModel).where(SkillTemplateModel.user_id == user_id)

            result = await session.execute(query.order_by(SkillTemplateModel.name))
            return [self._to_domain(m) for m in result.scalars().all()]

    async def get(self, skill_id: str) -> Optional[SkillTemplate]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(SkillTemplateModel).where(SkillTemplateModel.id == int(skill_id))
            )
            m = result.scalar_one_or_none()
            return self._to_domain(m) if m else None

    async def create(self, user_id: int, **kwargs) -> SkillTemplate:
        now = now_iso()
        async with async_session_maker() as session:
            model = SkillTemplateModel(
                user_id=user_id,
                name=kwargs.get("name", ""),
                display_name=kwargs.get("display_name", ""),
                description=kwargs.get("description", ""),
                version=kwargs.get("version", "1.0.0"),
                category=kwargs.get("category", "custom"),
                system_prompt=kwargs.get("system_prompt", ""),
                tool_names=json.dumps(kwargs.get("tool_names", [])),
                config_json=kwargs.get("config_json", "{}"),
                status="draft",
                is_default=1 if kwargs.get("is_default") else 0,
                created_at=now, updated_at=now,
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def update(self, skill_id: str, **kwargs) -> Optional[SkillTemplate]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(SkillTemplateModel).where(SkillTemplateModel.id == int(skill_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return None
            for key, value in kwargs.items():
                if value is None:
                    continue
                if key == "tool_names":
                    setattr(model, key, json.dumps(value))
                elif hasattr(model, key):
                    setattr(model, key, value)
            model.updated_at = now_iso()
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def delete(self, skill_id: str) -> bool:
        async with async_session_maker() as session:
            await session.execute(delete(UserSkillModel).where(UserSkillModel.template_id == int(skill_id)))
            result = await session.execute(delete(SkillTemplateModel).where(SkillTemplateModel.id == int(skill_id)))
            await session.commit()
            return result.rowcount > 0

    async def submit_review(self, skill_id: str) -> Optional[SkillTemplate]:
        return await self.update(skill_id, status="pending")

    async def review(self, skill_id: str, reviewer_id: int, approved: bool, comment: str = "") -> Optional[SkillTemplate]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(SkillTemplateModel).where(SkillTemplateModel.id == int(skill_id))
            )
            model = result.scalar_one_or_none()
            if not model:
                return None
            model.status = "approved" if approved else "rejected"
            model.reviewed_by = reviewer_id
            model.review_comment = comment
            model.is_public = 1 if approved else 0
            model.updated_at = now_iso()
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def install(self, user_id: int, template_id: int) -> bool:
        async with async_session_maker() as session:
            existing = await session.execute(
                select(UserSkillModel).where(
                    and_(UserSkillModel.user_id == user_id, UserSkillModel.template_id == template_id)
                )
            )
            if existing.scalar_one_or_none():
                return True
            now = now_iso()
            session.add(UserSkillModel(user_id=user_id, template_id=template_id, is_active=1, created_at=now, updated_at=now))
            await session.commit()
            return True

    async def uninstall(self, user_id: int, template_id: int) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(
                delete(UserSkillModel).where(
                    and_(UserSkillModel.user_id == user_id, UserSkillModel.template_id == template_id)
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def create_default_skills(self, admin_user_id: int):
        existing = await self.list_visible(admin_user_id, "my")
        if any(s.name == "general_assistant" for s in existing):
            return

        defaults = [
            {"name": "general_assistant", "display_name": "通用助手", "description": "通用AI助手，支持对话、文件操作、命令执行等", "category": "general", "system_prompt": "你是一个中文AI助手。你可以使用工具执行文件操作、运行命令、获取当前时间等。请根据用户需求灵活使用工具。", "tool_names": ["read_file","write_file","execute_command","get_current_time","list_directory"]},
            {"name": "code_assistant", "display_name": "代码助手", "description": "专注于代码编写、调试和分析", "category": "development", "system_prompt": "你是一个专业的代码助手。请帮助用户编写、调试和优化代码。可以使用工具来创建文件、运行代码和检查结果。", "tool_names": ["read_file","write_file","execute_command","list_directory"]},
            {"name": "file_manager", "display_name": "文件管理", "description": "文件和目录管理操作", "category": "system", "system_prompt": "你是一个文件管理助手。帮助用户创建、读取、修改、删除文件和目录。所有操作必须在允许的路径范围内进行。", "tool_names": ["read_file","write_file","list_directory","create_directory","delete_file","copy_file","move_file"]},
            {"name": "web_tools", "display_name": "网络工具", "description": "HTTP请求、网页抓取、API调用", "category": "network", "system_prompt": "你可以使用HTTP请求工具发送网络请求，使用网页抓取工具获取网页内容。", "tool_names": ["http_request","web_scraper","download_file"]},
            {"name": "data_processor", "display_name": "数据处理", "description": "JSON解析、CSV处理、数据转换、编码解码等", "category": "data", "system_prompt": "你是一个数据处理助手。可以使用工具进行JSON解析、CSV处理、数据格式转换、编码解码等操作。", "tool_names": ["parse_json","json_path","csv_process","data_transform","format_data","url_codec","base64_codec"]},
        ]

        for d in defaults:
            await self.create(user_id=admin_user_id, is_default=True, **d)
            s = await self.list_visible(admin_user_id, "my")
            created = next((x for x in s if x.name == d["name"]), None)
            if created:
                await self.review(str(created.id), admin_user_id, approved=True)
        logger.info(f"Created {len(defaults)} default skills")

    def _to_domain(self, m: SkillTemplateModel) -> SkillTemplate:
        tool_names = []
        try:
            tool_names = json.loads(m.tool_names) if m.tool_names else []
        except Exception:
            pass
        return SkillTemplate(
            id=str(m.id),
            user_id=str(m.user_id),
            name=m.name,
            display_name=m.display_name or "",
            description=m.description or "",
            version=m.version or "1.0.0",
            category=m.category or "custom",
            system_prompt=m.system_prompt or "",
            tool_names=tool_names,
            config_json=m.config_json or "{}",
            status=m.status or "draft",
            review_comment=m.review_comment or "",
            reviewed_by=str(m.reviewed_by) if m.reviewed_by else None,
            is_default=bool(m.is_default),
            is_public=bool(m.is_public),
            scope=m.scope or "private",
            team_id=str(m.team_id) if m.team_id else None,
            created_at=m.created_at or "",
            updated_at=m.updated_at or "",
        )
