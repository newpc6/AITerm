import json
import asyncio
import logging
import os
import re
from typing import List, Dict, Any, Optional

from app.repositories.tool import ToolRepository
from app.models.tool import Tool

logger = logging.getLogger("aiterm")


class ToolService:
    def __init__(self, sandbox_paths: List[str] = None):
        self.tool_repo = ToolRepository()
        self.sandbox_paths = sandbox_paths or []

    def validate_path_in_sandbox(self, path: str) -> bool:
        if not self.sandbox_paths:
            return True

        abs_path = os.path.abspath(path).lower()
        for sandbox_path in self.sandbox_paths:
            sandbox_abs = os.path.abspath(sandbox_path).lower()
            if abs_path.startswith(sandbox_abs):
                return True
        return False

    async def check_arguments_safety(self, tool: Tool, arguments: Dict[str, Any]) -> tuple[bool, str]:
        if not tool.sandbox_only:
            return True, ""

        path_keys = ["path", "file_path", "dir_path",
                     "directory", "source", "destination", "target", "save_path"]

        for key in path_keys:
            if key in arguments:
                path = arguments[key]
                if not self.validate_path_in_sandbox(path):
                    return False, f"路径 '{path}' 不在沙盒允许范围内，操作被拒绝。"

        delete_keywords = ["delete", "remove", "unlink", "rmdir"]
        if any(kw in tool.name.lower() for kw in delete_keywords):
            return True, "DELETE_CONFIRM_REQUIRED"

        return True, ""

    async def get_openai_tools(self) -> List[Dict[str, Any]]:
        tools = await self.tool_repo.list_tools(enabled_only=True)
        openai_tools = []
        for tool in tools:
            parameters = tool.parameters or {
                "type": "object", "properties": {}, "required": []}
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or tool.display_name or tool.name,
                    "parameters": parameters
                }
            }
            openai_tools.append(openai_tool)
        return openai_tools

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool = await self.tool_repo.get_tool_by_name(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")

        if not tool.enabled:
            raise ValueError(f"Tool '{name}' is disabled")

        is_safe, message = await self.check_arguments_safety(tool, arguments)
        if not is_safe:
            raise ValueError(message)

        if message == "DELETE_CONFIRM_REQUIRED":
            logger.warning(
                f"Delete operation requires confirmation: {name} with arguments {arguments}")

        try:
            result = await self._execute_tool_code(tool, arguments)
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    async def _execute_tool_code(self, tool: Tool, arguments: Dict[str, Any]) -> Any:
        logger.debug(f"Tool code for '{tool.name}':\n{tool.code[:500]}...")

        local_vars = {"arguments": arguments,
                      "result": None, "json": json, "asyncio": asyncio}

        wrapped_code = f"""
{tool.code}

if 'execute' in dir():
    result = execute(arguments)
"""

        exec_globals = {
            "__builtins__": __builtins__,
            "json": json,
            "asyncio": asyncio,
        }

        exec(wrapped_code, exec_globals, local_vars)

        result = local_vars.get("result")

        if asyncio.iscoroutine(result):
            result = await result

        return result

    async def process_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        results = []
        for tool_call in tool_calls:
            tool_call_id = tool_call.get("id", "")
            name = tool_call.get("name", "")
            arguments_str = tool_call.get("arguments", "{}")

            try:
                arguments = json.loads(arguments_str) if arguments_str else {}
            except json.JSONDecodeError:
                arguments = {}

            try:
                execution_result = await self.execute_tool(name, arguments)
                results.append({
                    "tool_call_id": tool_call_id,
                    "name": name,
                    "content": json.dumps(execution_result, ensure_ascii=False)
                })
            except Exception as e:
                results.append({
                    "tool_call_id": tool_call_id,
                    "name": name,
                    "content": json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
                })

        return results
