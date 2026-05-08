# isort: off
# fmt: off
"""
初始化系统配置脚本
运行此脚本可以导入默认的提示词和配置到数据库中

使用方法:
    python init_scripts/init_settings.py
"""

from sqlalchemy import select
import sys
import os
import asyncio
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

if os.path.exists(os.path.join(SCRIPT_DIR, "app")):
    PROJECT_DIR = SCRIPT_DIR
else:
    PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

from app.db.settings import SystemDictModel
from app.db.base import Base
from app.db import async_session_maker, engine
# fmt: on
# isort: on


DEFAULT_SETTINGS = {
    "chat_system_prompt": {
        "value": "你是一个中文 AI 助手，请直接回答用户问题，保持简洁、准确。当前选中节点：{{node_description}}。只有当用户问题涉及执行、部署、排障、环境差异时，再结合该节点上下文给出建议。\n\n你可以使用工具来获取信息或执行操作。当需要获取实时信息（如当前时间）或执行文件操作时，请调用相应的工具。\n\n如果最后会生成文件（如文档、zip、txt、doc等各种文件），不管用户是否要求生成文件下载链接，请使用 create_downloadable_file 工具。该工具会创建文件并返回下载链接，可以让用户直接点击下载，直接使用download_url字段的值，不要拼接sandbox等等其他内容。",
        "description": "对话系统提示词"
    },
    "chat_history_limit": {
        "value": "12",
        "description": "对话历史限制条数"
    },
    "max_iterations": {
        "value": "20",
        "description": "工具调用最大迭代次数"
    },
    "show_llm_input": {
        "value": "false",
        "description": "是否展示 LLM 输入内容"
    },
    "execution_command_blacklist": {
        "value": json.dumps(["del ", "delete ", "erase ", "rd ", "rmdir ", "rm ", "remove-item ", "format ", "shutdown ",
                            "reboot ", "restart-computer", "stop-service ", "sc stop ", "net stop ", "taskkill ", "kill ", "drop table ", "truncate table "]),
        "description": "命令黑名单列表"
    },
    "execution_command_whitelist": {
        "value": "[]",
        "description": "命令白名单列表"
    },
    "sandbox_paths": {
        "value": "[]",
        "description": "沙盒路径列表"
    },
    "sandbox_rules_prompt": {
        "value": "沙盒安全规则：\n1. 所有文件操作（读、写、删除、移动、复制）必须在沙盒路径内执行。\n2. 禁止访问沙盒路径之外的文件和目录。\n3. 禁止执行可能影响系统安全的操作（如修改系统配置、安装软件等）。\n4. 删除操作需要用户确认。\n5. 文件路径必须使用绝对路径。\n\n当前沙盒路径：{{sandbox_paths}}",
        "description": "沙盒安全规则提示词"
    },
    "llm_debug_logging": {
        "value": "false",
        "description": "是否启用 LLM 调试日志"
    }
}

DICT_CATEGORY = "global_settings"


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[完成] 数据库表检查/创建完成")


async def init_settings():
    await create_tables()

    async with async_session_maker() as session:
        added_count = 0
        updated_count = 0
        skipped_count = 0

        for key, data in DEFAULT_SETTINGS.items():
            result = await session.execute(
                select(SystemDictModel).where(
                    SystemDictModel.category == DICT_CATEGORY,
                    SystemDictModel.key == key
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                if existing.value != data["value"]:
                    existing.value = data["value"]
                    existing.description = data["description"]
                    updated_count += 1
                    print(f"[更新] 配置 '{key}'")
                else:
                    skipped_count += 1
                    print(f"[跳过] 配置 '{key}' 已存在且相同")
            else:
                from app.utils import now_iso
                now = now_iso()
                config = SystemDictModel(
                    category=DICT_CATEGORY,
                    key=key,
                    value=data["value"],
                    description=data["description"],
                    created_at=now,
                    updated_at=now
                )
                session.add(config)
                added_count += 1
                print(f"[添加] 配置 '{key}'")

        await session.commit()

        print(
            f"\n完成! 添加 {added_count} 个配置, 更新 {updated_count} 个配置, 跳过 {skipped_count} 个配置")


if __name__ == "__main__":
    print("=" * 50)
    print("AITerm 系统配置初始化脚本")
    print("=" * 50)
    print()
    asyncio.run(init_settings())
