import logging
from typing import List

from sqlalchemy import select, delete, and_
from app.db import async_session_maker
from app.db.team import TeamModel, TeamMemberModel
from app.db.user import UserModel
from app.models.team import TeamCreate
from app.utils import now_iso
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TeamOut(BaseModel):
    id: str; name: str; description: str; owner_id: str; owner_name: str = ""; member_count: int = 0; created_at: str = ""; updated_at: str = ""

    class Config: from_attributes = True


class TeamMemberOut(BaseModel):
    id: str; team_id: str; user_id: str; username: str = ""; display_name: str = ""; role: str; joined_at: str

    class Config: from_attributes = True


class TeamRepository:

    async def list_all(self) -> List[TeamOut]:
        async with async_session_maker() as session:
            result = await session.execute(select(TeamModel).order_by(TeamModel.name))
            teams = result.scalars().all()
            out = []
            for t in teams:
                owner_result = await session.execute(select(UserModel).where(UserModel.id == t.owner_id))
                owner = owner_result.scalar_one_or_none()
                cnt_result = await session.execute(select(TeamMemberModel).where(TeamMemberModel.team_id == t.id))
                members = cnt_result.scalars().all()
                out.append(TeamOut(id=str(t.id), name=t.name, description=t.description or "", owner_id=str(t.owner_id), owner_name=owner.display_name if owner else "", member_count=len(members), created_at=t.created_at, updated_at=t.updated_at))
            return out

    async def get(self, team_id: str) -> TeamOut | None:
        async with async_session_maker() as session:
            result = await session.execute(select(TeamModel).where(TeamModel.id == int(team_id)))
            t = result.scalar_one_or_none()
            if not t: return None
            owner_result = await session.execute(select(UserModel).where(UserModel.id == t.owner_id))
            owner = owner_result.scalar_one_or_none()
            cnt_result = await session.execute(select(TeamMemberModel).where(TeamMemberModel.team_id == t.id))
            members = cnt_result.scalars().all()
            return TeamOut(id=str(t.id), name=t.name, description=t.description or "", owner_id=str(t.owner_id), owner_name=owner.display_name if owner else "", member_count=len(members), created_at=t.created_at, updated_at=t.updated_at)

    async def create(self, payload: TeamCreate, owner_id: int) -> TeamOut:
        now = now_iso()
        async with async_session_maker() as session:
            t = TeamModel(name=payload.name, description=payload.description, owner_id=owner_id, created_at=now, updated_at=now)
            session.add(t)
            await session.commit()
            await session.refresh(t)
            session.add(TeamMemberModel(team_id=t.id, user_id=owner_id, role="owner", joined_at=now))
            await session.commit()
            return TeamOut(id=str(t.id), name=t.name, description=t.description or "", owner_id=str(owner_id), owner_name="", member_count=1, created_at=t.created_at, updated_at=t.updated_at)

    async def update(self, team_id: str, **kwargs) -> TeamOut | None:
        async with async_session_maker() as session:
            result = await session.execute(select(TeamModel).where(TeamModel.id == int(team_id)))
            t = result.scalar_one_or_none()
            if not t: return None
            for k, v in kwargs.items():
                if v is not None and hasattr(t, k):
                    setattr(t, k, v)
            t.updated_at = now_iso()
            await session.commit()
            return await self.get(team_id)

    async def delete(self, team_id: str) -> bool:
        async with async_session_maker() as session:
            await session.execute(delete(TeamMemberModel).where(TeamMemberModel.team_id == int(team_id)))
            result = await session.execute(delete(TeamModel).where(TeamModel.id == int(team_id)))
            await session.commit()
            return result.rowcount > 0

    async def list_members(self, team_id: str) -> List[TeamMemberOut]:
        async with async_session_maker() as session:
            result = await session.execute(select(TeamMemberModel).where(TeamMemberModel.team_id == int(team_id)))
            members = result.scalars().all()
            out = []
            for m in members:
                ur = await session.execute(select(UserModel).where(UserModel.id == m.user_id))
                u = ur.scalar_one_or_none()
                out.append(TeamMemberOut(id=str(m.id), team_id=str(m.team_id), user_id=str(m.user_id), username=u.username if u else "", display_name=u.display_name if u else "", role=m.role, joined_at=m.joined_at))
            return out

    async def add_member(self, team_id: str, user_id: int, role: str = "member") -> bool:
        async with async_session_maker() as session:
            existing = await session.execute(select(TeamMemberModel).where(and_(TeamMemberModel.team_id == int(team_id), TeamMemberModel.user_id == user_id)))
            if existing.scalar_one_or_none(): return False
            session.add(TeamMemberModel(team_id=int(team_id), user_id=user_id, role=role, joined_at=now_iso()))
            await session.commit()
            return True

    async def remove_member(self, team_id: str, user_id: int) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(delete(TeamMemberModel).where(and_(TeamMemberModel.team_id == int(team_id), TeamMemberModel.user_id == user_id)))
            await session.commit()
            return result.rowcount > 0

    async def update_member_role(self, team_id: str, user_id: int, role: str) -> bool:
        async with async_session_maker() as session:
            result = await session.execute(select(TeamMemberModel).where(and_(TeamMemberModel.team_id == int(team_id), TeamMemberModel.user_id == user_id)))
            m = result.scalar_one_or_none()
            if not m: return False
            m.role = role
            await session.commit()
            return True

    async def get_user_team_ids(self, user_id: int) -> List[int]:
        async with async_session_maker() as session:
            result = await session.execute(select(TeamMemberModel.team_id).where(TeamMemberModel.user_id == user_id))
            return [r for r in result.scalars().all()]
