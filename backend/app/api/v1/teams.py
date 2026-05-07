from fastapi import APIRouter, Depends, HTTPException

from app.models.common import Response
from app.models.team import TeamCreate, TeamMemberAdd, TeamMemberRole
from app.repositories.team import TeamRepository
from app.api.deps import get_current_user, require_admin

router = APIRouter(prefix="/teams", tags=["teams"])
repo = TeamRepository()


@router.get("")
async def list_teams(user=Depends(get_current_user)):
    if not user: raise HTTPException(401)
    teams = await repo.list_all()
    return Response(data=[t.model_dump() for t in teams])


@router.post("")
async def create_team(payload: TeamCreate, admin=Depends(require_admin)):
    team = await repo.create(payload, owner_id=int(admin.id))
    return Response(data=team.model_dump())


@router.get("/{team_id}")
async def get_team(team_id: str, user=Depends(get_current_user)):
    if not user: raise HTTPException(401)
    t = await repo.get(team_id)
    if not t: raise HTTPException(404, "Team not found")
    return Response(data=t.model_dump())


@router.put("/{team_id}")
async def update_team(team_id: str, payload: TeamCreate, admin=Depends(require_admin)):
    t = await repo.update(team_id, **payload.model_dump())
    if not t: raise HTTPException(404, "Team not found")
    return Response(data=t.model_dump())


@router.delete("/{team_id}")
async def delete_team(team_id: str, admin=Depends(require_admin)):
    if not await repo.delete(team_id): raise HTTPException(404, "Team not found")
    return Response(data={"status": "deleted"})


@router.get("/{team_id}/members")
async def list_members(team_id: str, user=Depends(get_current_user)):
    if not user: raise HTTPException(401)
    return Response(data=[m.model_dump() for m in await repo.list_members(team_id)])


@router.post("/{team_id}/members")
async def add_member(team_id: str, payload: TeamMemberAdd, admin=Depends(require_admin)):
    if not await repo.add_member(team_id, int(payload.user_id), payload.role):
        raise HTTPException(400, "Already a member")
    return Response(data={"status": "added"})


@router.delete("/{team_id}/members/{user_id}")
async def remove_member(team_id: str, user_id: str, admin=Depends(require_admin)):
    if not await repo.remove_member(team_id, int(user_id)):
        raise HTTPException(404, "Not found")
    return Response(data={"status": "removed"})


@router.put("/{team_id}/members/{user_id}")
async def update_member_role(team_id: str, user_id: str, payload: TeamMemberRole, admin=Depends(require_admin)):
    if not await repo.update_member_role(team_id, int(user_id), payload.role):
        raise HTTPException(404, "Not found")
    return Response(data={"status": "updated"})
