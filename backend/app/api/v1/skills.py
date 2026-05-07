import logging
from fastapi import APIRouter, HTTPException

from app.models.common import Response
from app.services.langchain.skill_registry import get_skill_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
async def list_skills(category: str = None):
    registry = get_skill_registry()
    skills = registry.list_by_category(category) if category else registry.list_all()
    return Response(data=[s.to_dict() for s in skills])


@router.get("/{skill_name}")
async def get_skill(skill_name: str):
    registry = get_skill_registry()
    skill = registry.get(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return Response(data=skill.to_dict())


@router.get("/{skill_name}/tools")
async def get_skill_tools(skill_name: str):
    registry = get_skill_registry()
    tools = registry.get_tools(skill_name)
    skill = registry.get(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return Response(data={"skill": skill_name, "tools": tools})
