from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {"code": 0, "message": "ok", "data": {"status": "ok"}}
