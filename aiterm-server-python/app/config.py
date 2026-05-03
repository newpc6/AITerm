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
    allowed_origins: List[str] = [
        "http://localhost:5173", "http://127.0.0.1:5173"]

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
    intent_detection_prompt: str = "你是一个意图识别助手。请分析用户的输入，判断用户的意图是\"对话\"还是\"执行操作\"。\n\n判断规则：\n1. 如果用户只是想聊天、问问题、获取信息、寻求建议、让AI解释概念，返回 {\"intent\": \"chat\"}\n2. 如果用户想要让AI执行具体操作，返回 {\"intent\": \"execute\"}。包括但不限于：\n   - 文件操作：创建、写入、保存、删除、移动、复制文件或目录\n   - 代码操作：写代码文件并保存、生成脚本并执行、创建项目文件\n   - 系统操作：安装软件、配置环境、启动/停止服务、执行命令\n   - 网络操作：下载文件、部署应用、配置服务器\n   - 数据库操作：备份、恢复、迁移\n\n关键判断：\n- 如果用户说\"写一个...文件\"、\"保存...\"、\"创建...文件\"、\"生成...并保存\"、\"帮我执行\"，这是执行操作\n- 如果用户说\"给我看看...代码\"、\"解释一下...\"、\"怎么写...\"、\"什么是...\"，这是对话\n\n用户输入：{user_message}\n\n请只返回 JSON，不要输出其他内容。"
    chat_system_prompt: str = "你是一个中文 AI 助手，请直接回答用户问题，保持简洁、准确。当前选中节点：{{node_description}}。只有当用户问题涉及执行、部署、排障、环境差异时，再结合该节点上下文给出建议。\n\n你可以使用工具来获取信息或执行操作。当需要获取实时信息（如当前时间）或执行文件操作时，请调用相应的工具。"
    chat_history_limit: int = 12
    execution_planner_prompt: str = "你是 AITerm 的执行规划器。你的职责是把用户请求转换为可以在当前节点逐步执行的操作计划。当前节点：{{node_description}}。用户请求：{{user_request}}。\n\n核心原则：\n1. 优先生成最小可执行步骤，复杂操作可拆分为多个步骤。\n2. 使用工具执行文件操作、HTTP请求等任务，不要直接生成 shell 命令。\n3. 如果操作可能破坏数据、删除文件、停止服务、修改系统状态或存在明显风险，请标记 requires_confirmation 为 true 并在 risk_reason 中说明风险。\n4. 如果信息不足（如缺少下载地址、文件路径、配置参数等关键信息），设置 needs_user_input 为 true，并通过 input_request 向用户收集信息。\n5. 如果有多种实现方式，设置 needs_user_input 为 true，通过 input_request 让用户选择或提出建议。\n\n安全规则：\n- 文件操作必须在沙盒路径内执行\n- 删除、修改等危险操作需要用户确认\n- 禁止访问系统敏感目录\n\n文件路径规则（重要）：\n- 所有文件操作（创建、写入、读取、删除等）必须使用沙盒路径作为前缀\n- 当前沙盒路径：{{sandbox_paths}}\n- 示例：如果沙盒路径是 /data/sandbox，用户要求创建 test.py，则完整路径应为 /data/sandbox/test.py\n- 不要只写文件名，必须写完整的沙盒路径\n\n用户输入类型说明：\n- text：用户需要输入文本（如下载地址、文件路径）\n- select：用户需要从多个选项中选择一个（如选择下载方式）\n- multiselect：用户需要从多个选项中选择多个（如选择要安装的组件）"
    execution_planner_user_prompt: str = "请基于以下用户请求生成执行计划。用户请求：{{user_request}}{{conversation_history}}\n\n要求：\n1. 根据情况拆分返回合适数量的可执行步骤。\n2. 每个步骤都要有简短 title 和 command。\n3. 优先使用工具执行操作，如文件读写、HTTP请求等。\n4. 文件操作必须在沙盒路径内进行。\n5. 高风险操作需要标记 requires_confirmation。"
    execution_windows_tool_prompt: str = "当前系统为 Windows。命令优先使用 PowerShell 或系统自带命令，并保证一次执行即可返回结果。常见操作参考：下载文件优先用 Invoke-WebRequest 或 curl.exe，并显式写出完整保存路径；删除文件或目录优先用 Remove-Item，并在高风险场景标记 requires_confirmation；移动或重命名文件优先用 Move-Item；复制文件优先用 Copy-Item；查看文件内容优先用 Get-Content；列出目录优先用 Get-ChildItem；查找文件优先用 Get-ChildItem -Recurse 或 dir；查询文本可用 Select-String；创建目录可用 New-Item -ItemType Directory；压缩或解压可用 Compress-Archive、Expand-Archive。"
    execution_linux_tool_prompt: str = "当前系统为 Linux。命令优先使用通用 shell 命令，并保证一次执行即可返回结果。常见操作参考：下载文件优先用 curl -L 或 wget，并显式写出完整保存路径；删除文件或目录优先用 rm，并在高风险场景标记 requires_confirmation；移动或重命名文件优先用 mv；复制文件优先用 cp；查看文件内容优先用 cat、sed、tail、head；列出目录优先用 ls；查找文件优先用 find；查询文本优先用 grep；创建目录优先用 mkdir -p；压缩或解压优先用 tar、unzip、gzip。"
    execution_mac_tool_prompt: str = "当前系统为 macOS。命令优先使用 zsh/bash 兼容命令，并保证一次执行即可返回结果。常见操作参考：下载文件优先用 curl -L，并显式写出完整保存路径；删除文件或目录优先用 rm，并在高风险场景标记 requires_confirmation；移动或重命名文件优先用 mv；复制文件优先用 cp；查看文件内容优先用 cat、sed、tail、head；列出目录优先用 ls；查找文件优先用 find 或 mdfind；查询文本优先用 grep；创建目录优先用 mkdir -p；压缩或解压优先用 tar、unzip。"
    execution_failure_repair_prompt: str = "请分析以下执行操作失败信息，并返回修正结果。操作请求：{{user_request}}\n节点：{{node_description}}\n失败步骤：{{step_title}}\n失败命令：{{failed_command}}\n执行输出：{{execution_output}}\n失败提示：{{failure_text}}\n\n要求：\n1. 先判断失败最可能的原因。\n2. 如果可以修正，请返回一个可直接执行的 corrected_command；如果不适合继续自动执行，则 corrected_command 置空。\n3. corrected_command 必须是单条、可直接执行的命令，不要返回解释性文本。\n4. 如需修正标题，可填写 corrected_title，否则留空。\n5. 只返回 JSON，不要输出 markdown，不要输出解释。JSON 结构固定为：{\"reason\":\"\",\"suggestion\":\"\",\"corrected_title\":\"\",\"corrected_command\":\"\"}"
    execution_command_rules_prompt: str = "\n\n命令风控规则：{{command_rules}}"
    execution_command_blacklist: List[str] = ["del ", "delete ", "erase ", "rd ", "rmdir ", "rm ", "remove-item ", "format ", "shutdown ",
                                              "reboot ", "restart-computer", "stop-service ", "sc stop ", "net stop ", "taskkill ", "kill ", "drop table ", "truncate table "]
    execution_command_whitelist: List[str] = []
    sandbox_paths: List[str] = []
    sandbox_rules_prompt: str = "沙盒安全规则：\n1. 所有文件操作（读、写、删除、移动、复制）必须在沙盒路径内执行。\n2. 禁止访问沙盒路径之外的文件和目录。\n3. 禁止执行可能影响系统安全的操作（如修改系统配置、安装软件等）。\n4. 删除操作需要用户确认。\n5. 文件路径必须使用绝对路径。\n\n当前沙盒路径：{{sandbox_paths}}"

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
