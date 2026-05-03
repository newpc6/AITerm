"""
完整初始化脚本
运行此脚本可以导入预设的工具和配置到数据库中

使用方法:
    cd aiterm-server-python
    python init_scripts/init_all.py
"""

from init_scripts.init_settings import init_settings
from init_scripts.init_tools import init_tools
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
