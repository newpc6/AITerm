from app.db import async_session_maker, engine
from sqlalchemy import text
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def migrate_data():
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"))
        tasks_exists = result.fetchone() is not None

        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='conversation_messages'"))
        messages_exists = result.fetchone() is not None

        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='chats'"))
        chats_exists = result.fetchone() is not None

        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"))
        new_messages_exists = result.fetchone() is not None

        if new_messages_exists:
            result = await conn.execute(text("SELECT COUNT(*) FROM messages"))
            count = result.scalar() or 0
            if count > 0:
                print("messages table already exists with data, skipping migration.")
                return
            else:
                print("messages table exists but is empty, dropping it...")
                await conn.execute(text("DROP TABLE messages"))
                new_messages_exists = False

        if chats_exists:
            result = await conn.execute(text("SELECT COUNT(*) FROM chats"))
            count = result.scalar() or 0
            if count > 0:
                print("chats table already exists with data, skipping migration.")
                return
            else:
                print("chats table exists but is empty, dropping it...")
                await conn.execute(text("DROP TABLE chats"))
                chats_exists = False

        if not tasks_exists and not messages_exists:
            print("No legacy tables found, nothing to migrate.")
            return

        print("Starting data migration...")

        await conn.execute(text("""
            CREATE TABLE chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(500) NOT NULL DEFAULT '',
                node_id INTEGER NOT NULL DEFAULT 1,
                model_id INTEGER,
                model_name VARCHAR(255),
                status VARCHAR(50) NOT NULL DEFAULT 'idle',
                summary TEXT NOT NULL DEFAULT '',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("Created chats table")

        await conn.execute(text("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role VARCHAR(50) NOT NULL,
                type VARCHAR(50) NOT NULL DEFAULT 'text',
                content TEXT NOT NULL,
                extra TEXT NOT NULL DEFAULT '{}',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("Created messages table")

        if tasks_exists:
            result = await conn.execute(text("""
                SELECT id, title, status, progress, conversation_id, node_id, model_id, model_name,
                       request, summary, steps_json, final_result, input_question, input_type,
                       input_options_json, input_placeholder, user_input, created_at, updated_at
                FROM tasks
                ORDER BY id
            """))
            tasks = result.fetchall()

            chat_id_map = {}
            for task in tasks:
                old_task_id = task[0]
                title = task[1] or ""
                status = task[2] or "idle"
                conversation_id = task[4]
                node_id = task[5] or 1
                model_id = task[6]
                model_name = task[7] or ""
                summary = task[9] or ""
                created_at_str = task[17]
                updated_at_str = task[18]

                try:
                    created_at = datetime.fromisoformat(created_at_str.replace(
                        'Z', '+00:00')) if created_at_str else datetime.now(timezone.utc)
                except:
                    created_at = datetime.now(timezone.utc)

                try:
                    updated_at = datetime.fromisoformat(updated_at_str.replace(
                        'Z', '+00:00')) if updated_at_str else datetime.now(timezone.utc)
                except:
                    updated_at = datetime.now(timezone.utc)

                result = await conn.execute(text("""
                    INSERT INTO chats (title, node_id, model_id, model_name, status, summary, created_at, updated_at)
                    VALUES (:title, :node_id, :model_id, :model_name, :status, :summary, :created_at, :updated_at)
                """), {
                    "title": title,
                    "node_id": node_id,
                    "model_id": model_id,
                    "model_name": model_name,
                    "status": status,
                    "summary": summary,
                    "created_at": created_at.isoformat(),
                    "updated_at": updated_at.isoformat()
                })

                new_chat_id = result.lastrowid
                chat_id_map[old_task_id] = new_chat_id

                request = task[8] or ""
                if request:
                    await conn.execute(text("""
                        INSERT INTO messages (chat_id, role, type, content, extra, created_at)
                        VALUES (:chat_id, 'user', 'text', :content, '{}', :created_at)
                    """), {
                        "chat_id": new_chat_id,
                        "content": request,
                        "created_at": created_at.isoformat()
                    })

                steps_json = task[10] or "[]"
                try:
                    steps = json.loads(steps_json)
                    for step in steps:
                        step_title = step.get("title", "")
                        step_command = step.get("command", "")
                        step_status = step.get("status", "pending")
                        step_output = step.get("result_output", "")

                        metadata = {
                            "step_index": step.get("index", 0),
                            "command": step_command,
                            "status": step_status,
                            "output": step_output
                        }

                        content = f"第 {step.get('index', 0)} 步: {step_title}"
                        if step_command:
                            content += f"\n命令: {step_command}"

                        await conn.execute(text("""
                            INSERT INTO messages (chat_id, role, type, content, extra, created_at)
                            VALUES (:chat_id, 'assistant', 'step', :content, :extra, :created_at)
                        """), {
                            "chat_id": new_chat_id,
                            "content": content,
                            "extra": json.dumps(metadata, ensure_ascii=False),
                            "created_at": updated_at.isoformat()
                        })
                except:
                    pass

                final_result = task[11] or ""
                if final_result:
                    await conn.execute(text("""
                        INSERT INTO messages (chat_id, role, type, content, extra, created_at)
                        VALUES (:chat_id, 'assistant', 'text', :content, '{}', :created_at)
                    """), {
                        "chat_id": new_chat_id,
                        "content": final_result,
                        "created_at": updated_at.isoformat()
                    })

            print(f"Migrated {len(tasks)} tasks to chats table")

        if messages_exists:
            result = await conn.execute(text("""
                SELECT id, conversation_id, role, content, created_at
                FROM conversation_messages
                ORDER BY id
            """))
            old_messages = result.fetchall()

            for msg in old_messages:
                old_conversation_id = msg[1]
                role = msg[2] or "user"
                content = msg[3] or ""
                created_at_str = msg[4]

                try:
                    created_at = datetime.fromisoformat(created_at_str.replace(
                        'Z', '+00:00')) if created_at_str else datetime.now(timezone.utc)
                except:
                    created_at = datetime.now(timezone.utc)

                chat_id = 1
                if old_conversation_id:
                    chat_id = old_conversation_id

                await conn.execute(text("""
                    INSERT INTO messages (chat_id, role, type, content, extra, created_at)
                    VALUES (:chat_id, :role, 'text', :content, '{}', :created_at)
                """), {
                    "chat_id": chat_id,
                    "role": role,
                    "content": content,
                    "created_at": created_at.isoformat()
                })

            print(
                f"Migrated {len(old_messages)} conversation_messages to messages table")

        await conn.commit()
        print("Data migration completed successfully!")

        print("\nYou can now safely delete the old tables:")
        print("  DROP TABLE tasks;")
        print("  DROP TABLE conversation_messages;")


if __name__ == "__main__":
    asyncio.run(migrate_data())
