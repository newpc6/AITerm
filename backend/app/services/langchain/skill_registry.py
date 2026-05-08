import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aiterm")


class SkillDefinition:
    def __init__(
        self,
        name: str = "",
        display_name: str = "",
        description: str = "",
        version: str = "1.0.0",
        category: str = "general",
        system_prompt: str = "",
        tools: List[str] = None,
        config: Dict[str, Any] = None,
    ):
        self.name = name
        self.display_name = display_name or name
        self.description = description
        self.version = version
        self.category = category
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.config = config or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "category": self.category,
            "system_prompt": self.system_prompt,
            "tools": self.tools,
            "config": self.config,
        }


class SkillRegistry:
    def __init__(self, skills_dir: str = None):
        self._skills: Dict[str, SkillDefinition] = {}
        self._builtin_skills: Dict[str, SkillDefinition] = {}
        self._skills_dir = skills_dir or str(Path(__file__).parent.parent.parent.parent / "data" / "skills")
        self._load_builtin_skills()

    def _load_builtin_skills(self):
        skills_path = Path(self._skills_dir)
        if not skills_path.exists():
            os.makedirs(skills_path, exist_ok=True)
            self._create_default_skills(skills_path)

        for file_path in skills_path.glob("*.json"):
            try:
                content = file_path.read_text(encoding='utf-8')
                data = json.loads(content)
                skill = SkillDefinition(
                    name=data.get("name", file_path.stem),
                    display_name=data.get("display_name", ""),
                    description=data.get("description", ""),
                    version=data.get("version", "1.0.0"),
                    category=data.get("category", "general"),
                    system_prompt=data.get("system_prompt", ""),
                    tools=data.get("tools", []),
                    config=data.get("config", {}),
                )
                self.register_builtin(skill)
                logger.info(f"Loaded skill: {skill.name}")
            except Exception as e:
                logger.error(f"Failed to load skill {file_path}: {e}")

    def _create_default_skills(self, path: Path):
        general_skill = {
            "name": "general_assistant",
            "display_name": "通用助手",
            "description": "通用AI助手，支持对话、文件操作、命令执行等",
            "version": "1.0.0",
            "category": "general",
            "system_prompt": "你是一个中文AI助手。你可以使用工具执行文件操作、运行命令、获取当前时间等。请根据用户需求灵活使用工具。",
            "tools": ["read_file", "write_file", "execute_command", "get_current_time", "list_directory"],
            "config": {}
        }
        (path / "general_assistant.json").write_text(json.dumps(general_skill, ensure_ascii=False, indent=2))

        code_skill = {
            "name": "code_assistant",
            "display_name": "代码助手",
            "description": "专注于代码编写、调试和分析",
            "version": "1.0.0",
            "category": "development",
            "system_prompt": "你是一个专业的代码助手。请帮助用户编写、调试和优化代码。可以使用工具来创建文件、运行代码和检查结果。",
            "tools": ["read_file", "write_file", "execute_command", "list_directory"],
            "config": {}
        }
        (path / "code_assistant.json").write_text(json.dumps(code_skill, ensure_ascii=False, indent=2))

        file_skill = {
            "name": "file_manager",
            "display_name": "文件管理",
            "description": "文件和目录管理操作",
            "version": "1.0.0",
            "category": "system",
            "system_prompt": "你是一个文件管理助手。帮助用户创建、读取、修改、删除文件和目录。所有操作必须在允许的路径范围内进行。",
            "tools": ["read_file", "write_file", "list_directory", "create_directory", "delete_file", "copy_file", "move_file"],
            "config": {}
        }
        (path / "file_manager.json").write_text(json.dumps(file_skill, ensure_ascii=False, indent=2))

        web_skill = {
            "name": "web_tools",
            "display_name": "网络工具",
            "description": "HTTP请求、网页抓取、API调用",
            "version": "1.0.0",
            "category": "network",
            "system_prompt": "你可以使用HTTP请求工具发送网络请求，使用网页抓取工具获取网页内容。",
            "tools": ["http_request", "web_scraper", "download_file"],
            "config": {}
        }
        (path / "web_tools.json").write_text(json.dumps(web_skill, ensure_ascii=False, indent=2))

        data_skill = {
            "name": "data_processor",
            "display_name": "数据处理",
            "description": "JSON解析、CSV处理、数据转换、编码解码等",
            "version": "1.0.0",
            "category": "data",
            "system_prompt": "你是一个数据处理助手。可以使用工具进行JSON解析、CSV处理、数据格式转换、编码解码等操作。",
            "tools": ["parse_json", "json_path", "csv_process", "data_transform", "format_data", "url_codec", "base64_codec"],
            "config": {}
        }
        (path / "data_processor.json").write_text(json.dumps(data_skill, ensure_ascii=False, indent=2))

        logger.info(f"Created {5} default skill definitions")

    def register_builtin(self, skill: SkillDefinition):
        self._builtin_skills[skill.name] = skill
        self._skills[skill.name] = skill

    def register(self, skill: SkillDefinition):
        self._skills[skill.name] = skill

    def unregister(self, name: str):
        if name in self._builtin_skills:
            raise ValueError(f"Cannot unregister built-in skill: {name}")
        self._skills.pop(name, None)

    def get(self, name: str) -> Optional[SkillDefinition]:
        return self._skills.get(name)

    def list_all(self) -> List[SkillDefinition]:
        return list(self._skills.values())

    def list_by_category(self, category: str) -> List[SkillDefinition]:
        return [s for s in self._skills.values() if s.category == category]

    def get_system_prompt(self, name: str) -> str:
        skill = self.get(name)
        return skill.system_prompt if skill else ""

    def get_tools(self, name: str) -> List[str]:
        skill = self.get(name)
        return skill.tools if skill else []

    def get_aggregated_prompt(self, skill_names: List[str], base_prompt: str = "") -> str:
        prompts = [base_prompt] if base_prompt else []
        for name in skill_names:
            skill = self.get(name)
            if skill and skill.system_prompt:
                prompts.append(f"[{skill.display_name}]\n{skill.system_prompt}")
        return "\n\n".join(prompts)


_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
    return _skill_registry
