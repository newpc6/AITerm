import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.models.common import Response
from app.models.skill import SkillTemplate, SkillCreate, SkillUpdate, SkillReview
from app.repositories.skill import SkillRepository
from app.db.skill import UserSkillModel
from app.db import async_session_maker
from app.api.deps import get_current_user, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/skills", tags=["skills"])
repo = SkillRepository()


async def _tag_installed(skills: list, user_id: int) -> list:
    if not skills:
        return skills
    async with async_session_maker() as session:
        skill_ids = [int(s.id) for s in skills]
        result = await session.execute(
            select(UserSkillModel.template_id).where(
                UserSkillModel.user_id == user_id,
                UserSkillModel.template_id.in_(skill_ids)
            )
        )
        installed_ids = {row[0] for row in result.all()}
    for s in skills:
        s.installed = int(s.id) in installed_ids
    return skills


@router.get("")
async def list_skills(scope: str = "my", user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    skills = await repo.list_visible(user_id=int(user.id), scope=scope)
    if scope in ("public", "installed", "my"):
        skills = await _tag_installed(skills, int(user.id))
    return Response(data=[s.model_dump() for s in skills])


@router.post("")
async def create_skill(payload: SkillCreate, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    skill = await repo.create(user_id=int(user.id), **payload.model_dump())
    return Response(data=skill.model_dump())


@router.get("/{skill_id}")
async def get_skill(skill_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    skill = await repo.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return Response(data=skill.model_dump())


@router.put("/{skill_id}")
async def update_skill(skill_id: str, payload: SkillUpdate, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    existing = await repo.get(skill_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Skill not found")
    if str(existing.user_id) != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Cannot edit this skill")
    update_data = {k: v for k, v in payload.model_dump().items()
                   if v is not None}
    skill = await repo.update(skill_id, **update_data)
    return Response(data=skill.model_dump() if skill else None)


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    existing = await repo.get(skill_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Skill not found")
    if str(existing.user_id) != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Cannot delete this skill")
    await repo.delete(skill_id)
    return Response(data={"status": "deleted"})


@router.post("/{skill_id}/submit")
async def submit_skill(skill_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    existing = await repo.get(skill_id)
    if not existing or str(existing.user_id) != user.id:
        raise HTTPException(status_code=404, detail="Skill not found")
    await repo.submit_review(skill_id)
    return Response(data={"status": "submitted"})


@router.post("/{skill_id}/withdraw")
async def withdraw_skill(skill_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    existing = await repo.get(skill_id)
    if not existing or str(existing.user_id) != user.id:
        raise HTTPException(status_code=404, detail="Skill not found")
    if existing.status != "pending":
        raise HTTPException(
            status_code=400, detail="Skill is not pending review")
    await repo.update(skill_id, status="draft")
    return Response(data={"status": "withdrawn"})


@router.post("/{skill_id}/review")
async def review_skill(skill_id: str, payload: SkillReview, admin=Depends(require_admin)):
    skill = await repo.review(skill_id, reviewer_id=int(admin.id), approved=payload.approved, comment=payload.comment)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return Response(data=skill.model_dump())


@router.post("/{skill_id}/install")
async def install_skill(skill_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    await repo.install(user_id=int(user.id), template_id=int(skill_id))
    return Response(data={"status": "installed"})


@router.delete("/{skill_id}/uninstall")
async def uninstall_skill(skill_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    await repo.uninstall(user_id=int(user.id), template_id=int(skill_id))
    return Response(data={"status": "uninstalled"})


@router.get("/installed/list")
async def installed_skills(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    skills = await repo.list_visible(user_id=int(user.id), scope="installed")
    return Response(data=[s.model_dump() for s in skills])
