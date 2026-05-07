import json
import logging
from typing import Any, Dict, List, Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model

logger = logging.getLogger("aiterm")


class AITermToolAdapter(BaseTool):
    name: str = ""
    description: str = ""
    _tool_data: Dict[str, Any] = {}
    _tool_service: Any = None
    _chat_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, tool_data: Dict[str, Any], tool_service: Any = None, chat_id: str = None, **kwargs):
        name = tool_data.get("name", "")
        description = tool_data.get("description", "") or tool_data.get("display_name", "")

        params_schema = tool_data.get("parameters", {})
        args_schema = self._build_args_schema(name, params_schema)

        super().__init__(name=name, description=description, args_schema=args_schema, **kwargs)
        self._tool_data = tool_data
        self._tool_service = tool_service
        self._chat_id = chat_id

    @staticmethod
    def _build_args_schema(name: str, params: Dict[str, Any]) -> Type[BaseModel]:
        properties = params.get("properties", {}) if params else {}
        required = params.get("required", []) if params else []

        fields: Dict[str, Any] = {}
        for prop_name, prop_info in properties.items():
            prop_type = str
            prop_description = prop_info.get("description", "")
            prop_default = prop_info.get("default")
            is_required = prop_name in (required if required else [])

            if prop_info.get("type") == "integer":
                prop_type = int
            elif prop_info.get("type") == "number":
                prop_type = float
            elif prop_info.get("type") == "boolean":
                prop_type = bool

            if is_required:
                fields[prop_name] = (prop_type, Field(description=prop_description))
            else:
                fields[prop_name] = (
                    Optional[prop_type],
                    Field(default=prop_default, description=prop_description),
                )

        if not fields:
            fields["args"] = (Dict[str, Any], Field(default={}, description="Tool arguments"))

        schema_name = f"{name.replace('-', '_').replace('.', '_')}_args"
        return create_model(schema_name, **fields)

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, **kwargs: Any) -> str:
        if not self._tool_service:
            return json.dumps({"success": False, "error": "Tool service not available"})

        try:
            result = await self._tool_service.execute_tool(
                self._tool_data.get("name", self.name),
                kwargs,
                chat_id=self._chat_id,
            )
            if isinstance(result, dict):
                return json.dumps(result, ensure_ascii=False)
            return str(result)
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
