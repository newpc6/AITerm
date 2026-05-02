from app.db.settings import ModelConfigModel, SystemDictModel, AuthSettingsModel
from app.db.message import MessageModel
from app.db.chat import ChatModel
from app.db.session import SessionModel
from app.db.user import UserModel
from app.db.node import NodeModel
from app.db.tool import ToolModel
import os
import logging
from typing import List, Set, Dict, Any, Type
from sqlalchemy import inspect, text, String, Text, Integer, Float, Boolean
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.sql import func

from app.config import get_settings
from app.db.base import Base

logger = logging.getLogger(__name__)

settings = get_settings()

db_path = settings.database.sqlite_path
os.makedirs(os.path.dirname(db_path), exist_ok=True)

DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


ALL_MODELS: List[Type[Base]] = [
    NodeModel,
    UserModel,
    SessionModel,
    ChatModel,
    MessageModel,
    ModelConfigModel,
    SystemDictModel,
    AuthSettingsModel,
    ToolModel,
]


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_table_columns_info(conn, table_name: str) -> Dict[str, Dict[str, Any]]:
    result = await conn.execute(text(f"PRAGMA table_info({table_name})"))
    rows = result.fetchall()
    columns = {}
    for row in rows:
        columns[row[1]] = {
            "cid": row[0],
            "name": row[1],
            "type": row[2],
            "notnull": row[3],
            "dflt_value": row[4],
            "pk": row[5]
        }
    return columns


async def table_exists(conn, table_name: str) -> bool:
    result = await conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name}
    )
    return result.fetchone() is not None


def get_default_value(column) -> str:
    if column.default is None:
        if isinstance(column.type, (String, Text)):
            return "DEFAULT ''"
        return ""

    default = column.default

    if hasattr(default, 'arg'):
        arg = default.arg
        if isinstance(arg, str):
            escaped = arg.replace("'", "''")
            return f"DEFAULT '{escaped}'"
        elif isinstance(arg, (int, float)):
            return f"DEFAULT {arg}"
        elif arg is None:
            if isinstance(column.type, (String, Text)):
                return "DEFAULT ''"
            return ""
        else:
            escaped = str(arg).replace("'", "''")
            return f"DEFAULT '{escaped}'"

    if isinstance(column.type, (String, Text)):
        return "DEFAULT ''"
    return ""


def get_sqlite_type(column) -> str:
    col_type = column.type.compile(dialect=None)
    col_type_lower = col_type.lower()

    if isinstance(column.type, Integer):
        return "INTEGER"
    elif isinstance(column.type, Float):
        return "REAL"
    elif isinstance(column.type, Boolean):
        return "INTEGER"
    elif isinstance(column.type, String):
        return f"VARCHAR({column.type.length or 255})"
    elif isinstance(column.type, Text):
        return "TEXT"
    else:
        return col_type


def types_compatible(db_type: str, model_type: str) -> bool:
    db_type_upper = db_type.upper()
    model_type_upper = model_type.upper()

    if db_type_upper == model_type_upper:
        return True

    type_groups = [
        {"INTEGER", "INT"},
        {"REAL", "FLOAT", "DOUBLE"},
        {"TEXT", "CLOB"},
        {"VARCHAR", "CHAR", "NCHAR", "NVARCHAR"}
    ]

    for group in type_groups:
        if db_type_upper in group and model_type_upper in group:
            return True

    if db_type_upper.startswith("VARCHAR") and model_type_upper.startswith("VARCHAR"):
        return True

    return False


async def rebuild_table(conn, model, existing_columns: Dict[str, Dict[str, Any]]):
    table_name = model.__tablename__
    mapper = inspect(model)
    model_columns = {c.key: c for c in mapper.columns}

    temp_table_name = f"{table_name}_temp_{os.getpid()}"

    pk_columns = [col_name for col_name,
                  col in model_columns.items() if col.primary_key]
    if not pk_columns:
        pk_columns = ["id"]

    create_cols = []
    for col_name, column in model_columns.items():
        col_type = get_sqlite_type(column)
        nullable = "NOT NULL" if not column.nullable else "NULL"
        default = get_default_value(column)
        pk_clause = "PRIMARY KEY" if col_name in pk_columns else ""
        create_cols.append(
            f"{col_name} {col_type} {nullable} {default} {pk_clause}".strip())

    create_sql = f"CREATE TABLE {temp_table_name} ({', '.join(create_cols)})"
    logger.info(f"Creating temp table: {temp_table_name}")
    await conn.execute(text(create_sql))

    common_columns = [col for col in model_columns.keys()
                      if col in existing_columns]
    select_cols = ", ".join(common_columns)
    insert_cols = ", ".join(common_columns)

    copy_sql = f"INSERT INTO {temp_table_name} ({insert_cols}) SELECT {select_cols} FROM {table_name}"
    logger.info(f"Copying data from {table_name} to {temp_table_name}")
    await conn.execute(text(copy_sql))

    drop_sql = f"DROP TABLE {table_name}"
    logger.info(f"Dropping old table: {table_name}")
    await conn.execute(text(drop_sql))

    rename_sql = f"ALTER TABLE {temp_table_name} RENAME TO {table_name}"
    logger.info(f"Renaming {temp_table_name} to {table_name}")
    await conn.execute(text(rename_sql))

    for index in model.__table__.indexes:
        try:
            await conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index.name} ON {table_name} ({', '.join([c.name for c in index.columns])})"))
        except Exception as e:
            logger.warning(f"Failed to create index {index.name}: {e}")


async def auto_migrate():
    async with engine.begin() as conn:
        for model in ALL_MODELS:
            table_name = model.__tablename__
            mapper = inspect(model)
            model_columns = {c.key: c for c in mapper.columns}

            if not await table_exists(conn, table_name):
                logger.info(f"Creating table: {table_name}")
                await conn.run_sync(lambda sync_conn: model.__table__.create(sync_conn))
                continue

            existing_columns = await get_table_columns_info(conn, table_name)

            needs_rebuild = False
            new_columns = []

            for col_name, column in model_columns.items():
                if col_name not in existing_columns:
                    new_columns.append(col_name)
                else:
                    db_col = existing_columns[col_name]
                    model_type = get_sqlite_type(column)
                    db_type = db_col["type"]

                    if not types_compatible(db_type, model_type):
                        logger.info(
                            f"Column {col_name} type changed from {db_type} to {model_type}, will rebuild table")
                        needs_rebuild = True

            if needs_rebuild:
                await rebuild_table(conn, model, existing_columns)
            else:
                for col_name in new_columns:
                    column = model_columns[col_name]
                    col_type = get_sqlite_type(column)
                    nullable = "NULL" if column.nullable else "NOT NULL"
                    default = get_default_value(column)

                    sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} {nullable} {default}"
                    logger.info(f"Adding column {col_name} to {table_name}")
                    await conn.execute(text(sql))

                    if column.default is not None and hasattr(column.default, 'arg'):
                        default_val = column.default.arg
                        if default_val is not None and default_val != "":
                            if isinstance(column.type, (String, Text)):
                                escaped = str(default_val).replace("'", "''")
                                update_sql = f"UPDATE {table_name} SET {col_name} = '{escaped}' WHERE {col_name} IS NULL OR {col_name} = ''"
                            else:
                                update_sql = f"UPDATE {table_name} SET {col_name} = {default_val} WHERE {col_name} IS NULL"
                            try:
                                await conn.execute(text(update_sql))
                                logger.info(
                                    f"Updated default values for {col_name}")
                            except Exception as e:
                                logger.warning(
                                    f"Failed to update default values for {col_name}: {e}")

        await conn.commit()

    logger.info("Database auto-migration completed")


async def init_db():
    await auto_migrate()
