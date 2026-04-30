from pydantic_settings import BaseSettings
from typing import List, Optional, Dict, Any
from functools import lru_cache


class DatabaseSettings(BaseSettings):
    driver: str = "sqlite"
    sqlite_path: str = "data/aiterm.db"
    mysql_dsn: str = ""

    class Config:
        env_prefix = "DB_"


class CORSSettings(BaseSettings):
    allowed_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    class Config:
        env_prefix = "CORS_"


class LogSettings(BaseSettings):
    enabled: bool = True
    request_body: int = 128
    response_body: int = 128

    class Config:
        env_prefix = "LOG_"


class LLMSettings(BaseSettings):
    api_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.7
    extra_params: Dict[str, Any] = {}
    extra_body: Dict[str, Any] = {}
    extra_headers: Dict[str, str] = {}
    chat_system_prompt: str = "你是一个中文 AI 助手，请直接回答用户问题，保持简洁、准确。当前选中节点：{{node_description}}。只有当用户问题涉及执行、部署、排障、环境差异时，再结合该节点上下文给出建议。"
    task_planner_prompt: str = "你是 AITerm 的任务规划器。你的职责是把用户请求转换为可以在当前节点逐步执行的任务计划。当前节点：{{node_description}}。用户请求：{{user_request}}。\n\n核心原则：\n1. 优先生成最小可执行步骤，复杂任务可拆分为多个步骤。\n2. 如果任务可能破坏数据、删除文件、停止服务、修改系统状态或存在明显风险，请标记 requires_confirmation 为 true 并在 risk_reason 中说明风险。\n3. 如果信息不足（如缺少下载地址、文件路径、配置参数等关键信息），设置 needs_user_input 为 true，并通过 input_request 向用户收集信息。\n4. 如果有多种实现方式，设置 needs_user_input 为 true，通过 input_request 让用户选择或提出建议。\n\n用户输入类型说明：\n- text：用户需要输入文本（如下载地址、文件路径）\n- select：用户需要从多个选项中选择一个（如选择下载方式）\n- multiselect：用户需要从多个选项中选择多个（如选择要安装的组件）\n\n示例场景：\n- 用户说'下载文件'但未提供地址 → 设置 needs_user_input=true，input_request.question='请提供要下载的文件地址'\n- 用户说'备份数据库'但未指定数据库类型 → 设置 needs_user_input=true，input_request.input_type='select'，options=['MySQL','PostgreSQL','SQLite']\n- 用户说'清理日志'但未指定哪些 → 设置 needs_user_input=true，input_request.input_type='multiselect'，options=['系统日志','应用日志','访问日志']"
    task_planner_user_prompt: str = "请基于以下用户请求生成任务计划，并为每一步提供可直接执行的命令。\n用户请求：{{user_request}}{{conversation_history}}\n\n要求：\n1. 根据情况拆分返回合适数量的可执行步骤。\n2. 每个步骤都要有简短 title 和 command。\n3. command 必须可直接在目标节点 shell 中执行，不要生成仅用于打开交互式终端的命令，例如 cmd.exe、powershell.exe、bash、sh。\n4. 优先在命令和结果中直接转换为更适合人查看的单位和格式。"
    task_windows_tool_prompt: str = "当前系统为 Windows。命令优先使用 PowerShell 或系统自带命令，并保证一次执行即可返回结果。常见操作参考：下载文件优先用 Invoke-WebRequest 或 curl.exe，并显式写出完整保存路径；删除文件或目录优先用 Remove-Item，并在高风险场景标记 requires_confirmation；移动或重命名文件优先用 Move-Item；复制文件优先用 Copy-Item；查看文件内容优先用 Get-Content；列出目录优先用 Get-ChildItem；查找文件优先用 Get-ChildItem -Recurse 或 dir；查询文本可用 Select-String；创建目录可用 New-Item -ItemType Directory；压缩或解压可用 Compress-Archive、Expand-Archive。"
    task_linux_tool_prompt: str = "当前系统为 Linux。命令优先使用通用 shell 命令，并保证一次执行即可返回结果。常见操作参考：下载文件优先用 curl -L 或 wget，并显式写出完整保存路径；删除文件或目录优先用 rm，并在高风险场景标记 requires_confirmation；移动或重命名文件优先用 mv；复制文件优先用 cp；查看文件内容优先用 cat、sed、tail、head；列出目录优先用 ls；查找文件优先用 find；查询文本优先用 grep；创建目录优先用 mkdir -p；压缩或解压优先用 tar、unzip、gzip。"
    task_mac_tool_prompt: str = "当前系统为 macOS。命令优先使用 zsh/bash 兼容命令，并保证一次执行即可返回结果。常见操作参考：下载文件优先用 curl -L，并显式写出完整保存路径；删除文件或目录优先用 rm，并在高风险场景标记 requires_confirmation；移动或重命名文件优先用 mv；复制文件优先用 cp；查看文件内容优先用 cat、sed、tail、head；列出目录优先用 ls；查找文件优先用 find 或 mdfind；查询文本优先用 grep；创建目录优先用 mkdir -p；压缩或解压优先用 tar、unzip。"
    task_failure_repair_prompt: str = "请分析以下自动化任务失败信息，并返回修正结果。任务请求：{{user_request}}\n节点：{{node_description}}\n失败步骤：{{step_title}}\n失败命令：{{failed_command}}\n执行输出：{{execution_output}}\n失败提示：{{failure_text}}\n\n要求：\n1. 先判断失败最可能的原因。\n2. 如果可以修正，请返回一个可直接执行的 corrected_command；如果不适合继续自动执行，则 corrected_command 置空。\n3. corrected_command 必须是单条、可直接执行的命令，不要返回解释性文本。\n4. 如需修正标题，可填写 corrected_title，否则留空。\n5. 只返回 JSON，不要输出 markdown，不要输出解释。JSON 结构固定为：{\"reason\":\"\",\"suggestion\":\"\",\"corrected_title\":\"\",\"corrected_command\":\"\"}"
    task_command_rules_prompt: str = "\n\n命令风控规则：{{command_rules}}"
    task_command_blacklist: List[str] = ["del ", "delete ", "erase ", "rd ", "rmdir ", "rm ", "remove-item ", "format ", "shutdown ", "reboot ", "restart-computer", "stop-service ", "sc stop ", "net stop ", "taskkill ", "kill ", "drop table ", "truncate table "]
    task_command_whitelist: List[str] = []

    class Config:
        env_prefix = "LLM_"


class Settings(BaseSettings):
    port: int = 18084
    data_dir: str = "data"
    database: DatabaseSettings = DatabaseSettings()
    cors: CORSSettings = CORSSettings()
    log: LogSettings = LogSettings()
    llm: LLMSettings = LLMSettings()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
