import os
import sys
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from passlib.context import CryptContext

from app.config import get_settings
from app.api import api_router
from app.middleware import LoggingMiddleware
from app.db import init_db, async_session_maker
from app.repositories import (
    NodeRepository, UserRepository, ModelConfigRepository
)
from app.models import UserRole, UserStatus
from app.db.settings import AuthSettingsModel
from sqlalchemy import select

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("aiterm")
logger.setLevel(logging.INFO)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def ensure_bootstrap_data():
    node_repo = NodeRepository()
    nodes = await node_repo.list_nodes()
    if not nodes:
        from app.models import Node, NodeStatus
        local_node = Node(
            id="0",
            name="local",
            host="127.0.0.1",
            port=22,
            status=NodeStatus.ONLINE
        )
        await node_repo.create_node(local_node)
        logger.info("Created default local node")

    user_repo = UserRepository()
    admin_count = await user_repo.count_active_admins()
    if admin_count == 0:
        from app.models import User
        now = datetime.utcnow().isoformat()
        password_hash = pwd_context.hash("12345678")
        admin_user = User(
            id="0",
            username="admin",
            display_name="系统管理员",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            last_login_at="",
            created_at=now,
            updated_at=now
        )
        await user_repo.create_user(admin_user, password_hash)
        logger.info(
            "Created default admin user (username: admin, password: 12345678)")

    model_repo = ModelConfigRepository()
    models = await model_repo.list_models()
    if not models:
        from app.models import ModelConfig
        now = datetime.utcnow().isoformat()
        default_model = ModelConfig(
            id="0",
            name="默认模型",
            api_url="https://api.openai.com/v1",
            api_key="",
            model="gpt-4o-mini",
            temperature=0.7,
            extra_params={},
            is_default=True,
            created_at=now,
            updated_at=now
        )
        await model_repo.create_model(default_model)
        logger.info("Created default model config")

    await ensure_builtin_tools()

    async with async_session_maker() as session:
        result = await session.execute(select(AuthSettingsModel))
        auth_settings = result.scalar_one_or_none()
        if not auth_settings:
            auth_settings = AuthSettingsModel(
                enabled=1,
                allow_password_login=1,
                session_ttl_hours=24
            )
            session.add(auth_settings)
            await session.commit()
            logger.info("Created default auth settings (enabled=True)")
        elif auth_settings.enabled == 0:
            auth_settings.enabled = 1
            await session.commit()
            logger.info("Updated auth settings to enabled=True")


async def ensure_builtin_tools():
    from app.repositories.tool import ToolRepository

    BUILTIN_TOOL_NAMES = {
        "read_file", "write_file", "execute_command", "get_current_time",
        "list_directory", "create_directory", "delete_file", "copy_file", "move_file",
    }

    tools_dir = Path(__file__).parent / "tools"
    if not tools_dir.exists():
        logger.warning(f"Built-in tools directory not found: {tools_dir}")
        return

    tool_repo = ToolRepository()
    imported_count = 0
    skipped_count = 0
    corrected_count = 0

    for file_path in sorted(tools_dir.glob("*.json")):
        try:
            content = file_path.read_text(encoding='utf-8')
            data = json.loads(content)
            name = data.get('name', file_path.stem)
            if not name:
                logger.warning(
                    f"Tool name missing in {file_path.name}, skipping")
                continue

            is_builtin = name in BUILTIN_TOOL_NAMES

            existing = await tool_repo.get_tool_by_name(name)
            if existing:
                if existing.is_builtin != is_builtin:
                    await tool_repo.update_tool(
                        tool_id=existing.id,
                        is_builtin=is_builtin
                    )
                    corrected_count += 1
                    label = "builtin" if is_builtin else "normal"
                    logger.info(
                        f"Corrected tool '{name}' is_builtin -> {label}")
                else:
                    skipped_count += 1
                continue

            await tool_repo.create_tool(
                name=name,
                display_name=data.get('display_name'),
                description=data.get('description'),
                code=data.get('code', ''),
                parameters=data.get('parameters'),
                config_schema=data.get('config_schema'),
                enabled=data.get('enabled', True),
                sandbox_only=data.get('sandbox_only', False),
                is_builtin=is_builtin
            )
            imported_count += 1
            label = "builtin" if is_builtin else "normal"
            logger.info(f"Imported {label} tool: {name}")
        except Exception as e:
            logger.error(f"Failed to import tool {file_path.name}: {e}")

    if imported_count > 0 or corrected_count > 0:
        logger.info(
            f"Tools bootstrap: {imported_count} imported, {corrected_count} corrected, {skipped_count} already exist"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    os.makedirs(settings.data_dir, exist_ok=True)

    await init_db()

    await ensure_bootstrap_data()

    logger.info(f"AITerm server starting on port {settings.port}")
    logger.info(
        f"Database: {settings.database.driver} at {settings.database.sqlite_path}")

    yield

    logger.info("AITerm server shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AITerm API",
        description="AI 驱动的智能终端管理工具",
        version="1.0.0",
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(LoggingMiddleware)

    app.include_router(api_router)

    @app.get("/health")
    async def health():
        return {"code": 0, "message": "ok", "data": {"status": "ok"}}

    dist_path = Path(__file__).parent / "dist"
    if dist_path.exists():
        MIME_TYPES = {
            ".js": "application/javascript",
            ".mjs": "application/javascript",
            ".css": "text/css",
            ".html": "text/html",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
        }

        @app.get("/assets/{file_path:path}")
        async def serve_assets(file_path: str):
            full_path = dist_path / "assets" / file_path
            if full_path.exists() and full_path.is_file():
                suffix = full_path.suffix.lower()
                media_type = MIME_TYPES.get(suffix, "application/octet-stream")
                content = full_path.read_bytes()
                return Response(content=content, media_type=media_type)
            return Response(content=b"Not found", status_code=404)

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            file_path = dist_path / full_path
            if file_path.exists() and file_path.is_file():
                suffix = file_path.suffix.lower()
                media_type = MIME_TYPES.get(suffix, "application/octet-stream")
                content = file_path.read_bytes()
                return Response(content=content, media_type=media_type)
            return FileResponse(dist_path / "index.html")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True
    )
