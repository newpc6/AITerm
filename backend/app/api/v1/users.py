from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.models import Response, User, UserCreate, UserUpdate, UserResetPassword, UserRole
from app.models.common import PaginatedResponse
from app.services import UserService
from app.api.deps import get_user_service, get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    service: UserService = Depends(get_user_service),
    current_user = Depends(get_current_user)
):
    items, total = await service.list_users(page, page_size)
    paginated = PaginatedResponse.create(
        items=[user.model_dump() for user in items],
        total=total,
        page=page,
        page_size=page_size
    )
    return Response(data=paginated.model_dump())


@router.post("")
async def create_user(
    request: UserCreate,
    service: UserService = Depends(get_user_service),
    current_user = Depends(get_current_user)
):
    try:
        user = await service.create_user(request)
        return Response(data=user.model_dump())
    except ValueError as e:
        return Response(code=1003, message=str(e))


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    service: UserService = Depends(get_user_service)
):
    user = await service.get_user(user_id)
    if not user:
        return Response(code=4043, message="user not found")
    return Response(data=user.model_dump())


@router.put("/{user_id}")
async def update_user(
    user_id: str,
    request: UserUpdate,
    service: UserService = Depends(get_user_service),
    current_user = Depends(get_current_user)
):
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    user = await service.update_user(user_id, **update_data)
    if not user:
        return Response(code=4043, message="user not found")
    return Response(data=user.model_dump())


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
    current_user = Depends(get_current_user)
):
    try:
        success = await service.delete_user(user_id)
        if not success:
            return Response(code=4043, message="user not found")
        return Response(data={"user_id": user_id, "status": "deleted"})
    except ValueError as e:
        return Response(code=1003, message=str(e))


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    request: UserResetPassword,
    service: UserService = Depends(get_user_service),
    current_user = Depends(get_current_user)
):
    success = await service.reset_password(user_id, request.password)
    if not success:
        return Response(code=4043, message="user not found")
    return Response(data={"user_id": user_id, "status": "password_reset"})
