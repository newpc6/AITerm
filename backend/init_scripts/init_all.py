# isort: skip_file
# fmt: off
"""
完整初始化脚本
运行此脚本可以导入预设的工具和配置到数据库中

使用方法:
    python init_scripts/init_all.py
"""

import sys
import os
import asyncio

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

if os.path.exists(os.path.join(SCRIPT_DIR, "app")):
    PROJECT_DIR = SCRIPT_DIR
else:
    PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

from init_scripts.init_tools import init_tools
from init_scripts.init_settings import init_settings
# fmt: on


async def init_all():
    print("=" * 50)
    print("AITerm 完整初始化脚本")
    print("=" * 50)
    print()

    print("[1/2] 初始化工具...")
    print("-" * 50)
    await init_tools()
    print()

    print("[2/2] 初始化系统配置...")
    print("-" * 50)
    await init_settings()
    print()

    print("=" * 50)
    print("初始化完成!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(init_all())
