from pydantic_settings import BaseSettings
from typing import List, Optional, Dict, Any
from functools import lru_cache
import json
import os


class DatabaseSettings(BaseSettings):
    driver: str = "sqlite"
    sqlite_path: str = "data/aiterm.db"
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "aiterm"

    def get_mysql_dsn(self) -> str:
        return f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"


class CORSSettings(BaseSettings):
    allowed_origins: List[str] = [
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:18084", "http://127.0.0.1:18084"]


class LogSettings(BaseSettings):
    enabled: bool = True
    request_body: int = 128
    response_body: int = 128


class LLMSettings(BaseSettings):
    api_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.7
    extra_params: Dict[str, Any] = {}
    extra_body: Dict[str, Any] = {}
    extra_headers: Dict[str, str] = {}
    chat_system_prompt: str = "你是一个中文 AI 助手，请直接回答用户问题，保持简洁、准确。当前选中节点：{{node_description}}。只有当用户问题涉及执行、部署、排障、环境差异时，再结合该节点上下文给出建议。\n\n你可以使用工具来获取信息或执行操作。当需要获取实时信息（如当前时间）或执行文件操作时，请调用相应的工具。\n\n如果最后会生成文件（如文档、zip、txt、doc等各种文件），不管用户是否要求生成文件下载链接，请使用 create_downloadable_file 工具。该工具会创建文件并返回下载链接，可以让用户直接点击下载，直接使用download_url字段的值，不要拼接sandbox等等其他内容。"
    chat_history_limit: int = 12
    execution_command_blacklist: List[str] = ["del ", "delete ", "erase ", "rd ", "rmdir ", "rm ", "remove-item ", "format ", "shutdown ",
                                              "reboot ", "restart-computer", "stop-service ", "sc stop ", "net stop ", "taskkill ", "kill ", "drop table ", "truncate table "]
    execution_command_whitelist: List[str] = []
    sandbox_paths: List[str] = []
    sandbox_rules_prompt: str = "沙盒安全规则：\n1. 所有文件操作（读、写、删除、移动、复制）必须在沙盒路径内执行。\n2. 禁止访问沙盒路径之外的文件和目录。\n3. 禁止执行可能影响系统安全的操作（如修改系统配置、安装软件等）。\n4. 删除操作需要用户确认。\n5. 文件路径必须使用绝对路径。\n\n当前沙盒路径：{{sandbox_paths}}\n\n如果没有明确指的文件的路径，如果chat_id有值，尽可能新建chat_id的文件夹，再在里面创建操作文件"


def load_config_from_json() -> dict:
    config_paths = [
        os.path.join(os.path.dirname(__file__), "..", "configs", "app.json"),
        os.path.join(os.path.dirname(__file__), "..", "app.json"),
    ]

    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

    return {}


class Settings(BaseSettings):
    port: int = 18084
    data_dir: str = "data"
    database: DatabaseSettings = DatabaseSettings()
    cors: CORSSettings = CORSSettings()
    log: LogSettings = LogSettings()
    llm: LLMSettings = LLMSettings()

    def __init__(self, **kwargs):
        config_data = load_config_from_json()

        if "server" in config_data:
            if "port" in config_data["server"]:
                config_data["port"] = config_data["server"]["port"]
            del config_data["server"]

        if "database" in config_data:
            db_config = config_data["database"]
            config_data["database"] = DatabaseSettings(**db_config)
        if "cors" in config_data:
            config_data["cors"] = CORSSettings(**config_data["cors"])
        if "log" in config_data:
            config_data["log"] = LogSettings(**config_data["log"])
        if "llm" in config_data:
            config_data["llm"] = LLMSettings(**config_data["llm"])

        config_data.update(kwargs)
        super().__init__(**config_data)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
