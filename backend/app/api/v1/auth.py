from fastapi import APIRouter, Depends, Header
from typing import Optional

from app.models import Response, AuthStatus, AuthLoginData, UserLogin, AuthChangePassword
from app.services import AuthService
from app.api.deps import get_auth_service, get_current_user_optional, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status")
async def get_auth_status(
    service: AuthService = Depends(get_auth_service),
    authorization: Optional[str] = Header(None)
):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    status = await service.get_status(token)
    return Response(data=status.model_dump())


@router.post("/login")
async def login(
    request: UserLogin,
    service: AuthService = Depends(get_auth_service)
):
    try:
        result = await service.login(request.username, request.password)
        return Response(data=result.model_dump())
    except ValueError as e:
        return Response(code=4010, message=str(e))


@router.post("/logout")
async def logout(
    service: AuthService = Depends(get_auth_service),
    authorization: Optional[str] = Header(None)
):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    if token:
        await service.logout(token)

    return Response(data={"status": "logged_out"})


@router.get("/me")
async def get_current_user_info(
    user = Depends(get_current_user)
):
    if not user:
        return Response(code=4011, message="unauthorized")
    return Response(data=user.model_dump())


@router.post("/change-password")
async def change_password(
    request: AuthChangePassword,
    user = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service)
):
    if not user:
        return Response(code=4011, message="unauthorized")

    try:
        await service.change_password(user.id, request.current_password, request.new_password)
        return Response(data={"status": "password_changed"})
    except ValueError as e:
        return Response(code=4010, message=str(e))
