import json
import re
from typing import List, Optional, Dict, Any, AsyncGenerator, Union
from datetime import datetime
import httpx

from app.config import LLMSettings
from app.models import (
    Node, TaskPlanStep, TaskPlanResult, UserInputRequest,
    TaskFailureRepairResult, ConversationMessage, TaskStep, ModelConfig
)
from app.services.command import detect_platform, describe_node
import logging

logger = logging.getLogger("aiterm")

class LLMClient:
    def __init__(self, settings: Union[LLMSettings, ModelConfig]):
        self.settings = settings
        self.timeout = 90.0

    @property
    def api_url(self) -> str:
        return self.settings.api_url

    @property
    def api_key(self) -> str:
        return self.settings.api_key

    @property
    def model(self) -> str:
        return self.settings.model

    @property
    def temperature(self) -> float:
        return self.settings.temperature

    @property
    def extra_params(self) -> Dict[str, Any]:
        if hasattr(self.settings, 'extra_params'):
            return self.settings.extra_params or {}
        return {}

    @property
    def extra_body(self) -> Dict[str, Any]:
        if hasattr(self.settings, 'extra_body'):
            return self.settings.extra_body or {}
        return {}

    @property
    def extra_headers(self) -> Dict[str, str]:
        if hasattr(self.settings, 'extra_headers'):
            return self.settings.extra_headers or {}
        return {}

    def _build_chat_url(self) -> str:
        url = self.api_url.rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        return f"{url}/chat/completions"

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.extra_headers:
            headers.update(self.extra_headers)
        return headers

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        stream: bool = False
    ) -> str:
        if not self.api_url or not self.model:
            raise ValueError("LLM 设置未完成，请先在设置页填写 API 地址和模型")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature or 0.7,
            "stream": stream
        }

        if self.extra_params:
            payload.update(self.extra_params)

        if self.extra_body:
            payload.update(self.extra_body)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._build_chat_url(),
                headers=self._get_headers(),
                json=payload
            )

            if response.status_code >= 400:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                if "error" in error_data and error_data["error"].get("message"):
                    raise ValueError(error_data["error"]["message"])
                raise ValueError(f"模型请求失败: HTTP {response.status_code}")

            data = response.json()
            if "choices" not in data or len(data["choices"]) == 0:
                raise ValueError("模型未返回有效回复")
            logger.info(f"模型返回数据: {data}")
            content = data["choices"][0].get("message", {}).get("content", "")
            if isinstance(content, list):
                content = "\n".join(
                    item.get("text", "") for item in content
                    if isinstance(item, dict) and "text" in item
                )

            if not content.strip():
                raise ValueError("模型返回内容为空")

            return content.strip()

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None
    ) -> AsyncGenerator[str, None]:
        if not self.api_url or not self.model:
            raise ValueError("LLM 设置未完成，请先在设置页填写 API 地址和模型")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature or 0.7,
            "stream": True
        }

        if self.extra_params:
            payload.update(self.extra_params)

        if self.extra_body:
            payload.update(self.extra_body)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                self._build_chat_url(),
                headers=self._get_headers(),
                json=payload
            ) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    try:
                        error_data = json.loads(body)
                        if "error" in error_data and error_data["error"].get("message"):
                            raise ValueError(error_data["error"]["message"])
                    except json.JSONDecodeError:
                        pass
                    raise ValueError(f"模型请求失败: HTTP {response.status_code}")

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue

                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        if "error" in data and data["error"].get("message"):
                            raise ValueError(data["error"]["message"])

                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if isinstance(content, list):
                                content = "\n".join(
                                    item.get("text", "") for item in content
                                    if isinstance(item, dict) and "text" in item
                                )
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue


class TaskPlanner:
    def __init__(self, settings: LLMSettings):
        self.settings = settings
        self.llm_client = LLMClient(settings)

    def _build_system_prompt(self, node: Node, request: str) -> str:
        template = self.settings.task_planner_prompt or "你是一个任务规划器，请将用户请求转换为可执行任务计划。"
        command_rules = self._build_command_rules()
        node_desc = describe_node(node)

        prompt = template.replace("{{node_description}}", node_desc)
        prompt = prompt.replace("{{user_request}}", request)
        prompt += command_rules
        prompt += """

你必须只返回 JSON，不要输出 markdown，不要输出解释。JSON 结构如下：

1. 正常任务计划：
{"title":"任务标题","summary":"任务摘要","requires_confirmation":false,"risk_reason":"","needs_user_input":false,"steps":[{"title":"步骤标题","command":"具体命令"}]}

2. 需要用户补充信息时（如缺少下载地址、文件路径等关键信息）：
{"title":"任务标题","summary":"需要用户补充信息","requires_confirmation":false,"risk_reason":"","needs_user_input":true,"input_request":{"question":"请提供下载地址","input_type":"text","options":[],"placeholder":"输入下载地址","default_value":""},"steps":[]}

3. 需要用户选择方案时（有多种实现方式）：
{"title":"任务标题","summary":"请选择实现方案","requires_confirmation":false,"risk_reason":"","needs_user_input":true,"input_request":{"question":"请选择下载方式","input_type":"select","options":["直接下载","使用代理下载","使用镜像站"],"placeholder":"","default_value":"直接下载"},"steps":[]}

input_type 可选值：text（文本输入）、select（单选）、multiselect（多选）
如果信息充足，直接生成 steps；如果信息不足或需要用户选择，设置 needs_user_input 为 true 并填写 input_request。"""

        return prompt

    def _build_user_prompt(
        self,
        node: Node,
        request: str,
        history: List[ConversationMessage]
    ) -> str:
        template = self.settings.task_planner_user_prompt or "请基于以下用户请求生成任务计划。"
        node_desc = describe_node(node)
        history_text = self._build_history_text(history)
        platform_name, platform_prompt = self._build_platform_prompt(node)

        prompt = template.replace("{{user_request}}", request)
        prompt = prompt.replace("{{conversation_history}}", history_text)
        prompt = prompt.replace("{{platform_name}}", platform_name)
        prompt = prompt.replace("{{platform_tool_prompt}}", platform_prompt)

        if platform_prompt:
            prompt += f"\n\n当前系统工具参考（{platform_name}）：\n{platform_prompt}"

        return prompt

    def _build_history_text(self, history: List[ConversationMessage]) -> str:
        if not history:
            return ""

        recent = history[-6:] if len(history) > 6 else history
        lines = ["\n\n最近对话上下文："]
        for msg in recent:
            if msg.role in ["user", "assistant"]:
                lines.append(f"- {msg.role}: {msg.content.strip()}")

        return "\n".join(lines)

    def _build_platform_prompt(self, node: Node) -> tuple:
        platform = detect_platform(node)
        if platform == "windows":
            return "Windows", self.settings.task_windows_tool_prompt
        elif platform == "linux":
            return "Linux", self.settings.task_linux_tool_prompt
        elif platform == "macos":
            return "macOS", self.settings.task_mac_tool_prompt
        return "未知", ""

    def _build_command_rules(self) -> str:
        blacklist = self.settings.task_command_blacklist or []
        whitelist = self.settings.task_command_whitelist or []

        if not blacklist and not whitelist:
            return ""

        rules = []
        if blacklist:
            rules.append(f"- 以下命令片段命中后会强制人工确认，请尽量避免误触：{'、'.join(blacklist)}")
        if whitelist:
            rules.append(f"- 以下命令片段属于白名单，可在生成命令时参考：{'、'.join(whitelist)}")

        template = self.settings.task_command_rules_prompt or "\n\n命令风控规则：{{command_rules}}"
        return "\n\n" + template.replace("{{command_rules}}", "\n".join(rules))

    async def generate_plan(
        self,
        node: Node,
        request: str,
        history: List[ConversationMessage]
    ) -> TaskPlanResult:
        messages = [
            {"role": "system", "content": self._build_system_prompt(node, request)},
            {"role": "user", "content": self._build_user_prompt(node, request, history)}
        ]

        response = await self.llm_client.chat(messages, temperature=0.2)
        return self._parse_plan(response)

    def _parse_plan(self, raw: str) -> TaskPlanResult:
        cleaned = raw.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start:end + 1]

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            repaired = self._repair_json(cleaned)
            data = json.loads(repaired)

        steps = []
        for step in data.get("steps", []):
            command = step.get("command", "").strip()
            if command:
                steps.append(TaskPlanStep(
                    title=step.get("title", "").strip(),
                    command=command
                ))

        input_request = None
        if data.get("needs_user_input") and data.get("input_request"):
            ir = data["input_request"]
            input_request = UserInputRequest(
                question=ir.get("question", "").strip(),
                input_type=ir.get("input_type", "text"),
                options=ir.get("options", []),
                placeholder=ir.get("placeholder", "").strip(),
                default_value=ir.get("default_value", "").strip()
            )

        return TaskPlanResult(
            title=data.get("title", "").strip() or "模型生成任务",
            summary=data.get("summary", "").strip() or "模型已生成执行计划。",
            requires_confirmation=data.get("requires_confirmation", False),
            risk_reason=data.get("risk_reason", "").strip(),
            needs_user_input=data.get("needs_user_input", False),
            input_request=input_request,
            steps=steps
        )

    def _repair_json(self, raw: str) -> str:
        result = []
        in_string = False
        escaped = False

        for ch in raw:
            if not in_string:
                result.append(ch)
                if ch == '"':
                    in_string = True
                continue

            if escaped:
                if ch not in '"\\/bfnrtu':
                    result.append('\\')
                result.append(ch)
                escaped = False
                continue

            if ch == '\\':
                result.append(ch)
                escaped = True
                continue

            result.append(ch)
            if ch == '"':
                in_string = False

        return ''.join(result)


class TaskRepairer:
    def __init__(self, settings: LLMSettings):
        self.settings = settings
        self.llm_client = LLMClient(settings)

    async def repair(
        self,
        node: Node,
        request: str,
        step: TaskStep,
        outputs: List[str],
        failure_text: str
    ) -> TaskFailureRepairResult:
        prompt = self._build_prompt(node, request, step, outputs, failure_text)
        response = await self.llm_client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return self._parse_result(response, step)

    def _build_prompt(
        self,
        node: Node,
        request: str,
        step: TaskStep,
        outputs: List[str],
        failure_text: str
    ) -> str:
        template = self.settings.task_failure_repair_prompt or "请分析以下自动化任务失败信息。"
        node_desc = describe_node(node)

        prompt = template.replace("{{node_description}}", node_desc)
        prompt = prompt.replace("{{user_request}}", request)
        prompt = prompt.replace("{{step_title}}", step.title)
        prompt = prompt.replace("{{failed_command}}", step.command)
        prompt = prompt.replace("{{execution_output}}", "\n".join(outputs) if outputs else "无输出")
        prompt = prompt.replace("{{failure_text}}", failure_text)

        return prompt

    def _parse_result(self, raw: str, step: TaskStep) -> TaskFailureRepairResult:
        cleaned = raw.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start:end + 1]

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return TaskFailureRepairResult()

        result = TaskFailureRepairResult(
            reason=data.get("reason", "").strip(),
            suggestion=data.get("suggestion", "").strip(),
            corrected_title=data.get("corrected_title", "").strip(),
            corrected_command=data.get("corrected_command", "").strip()
        )

        if not result.corrected_command:
            result.corrected_command = self._infer_command(raw, step)

        return result

    def _infer_command(self, text: str, step: TaskStep) -> str:
        pattern = r"`([^`\r\n]+)`"
        matches = re.findall(pattern, text)

        for match in matches:
            candidate = match.strip().strip("\"'")
            if candidate and not any(kw in candidate.lower() for kw in ["json", "markdown", "reason", "suggestion"]):
                if len(candidate) <= 300:
                    return candidate

        return ""


class ChatService:
    def __init__(self, settings: Union[LLMSettings, ModelConfig], chat_system_prompt: str = ""):
        self.settings = settings
        self.chat_system_prompt = chat_system_prompt
        self.llm_client = LLMClient(settings)

    def _build_system_prompt(self, node: Node) -> str:
        template = self.chat_system_prompt or "你是一个中文 AI 助手，请直接回答用户问题，保持简洁、准确。"
        node_desc = describe_node(node)
        return template.replace("{{node_description}}", node_desc)

    async def chat(
        self,
        node: Node,
        history: List[ConversationMessage],
        message: str
    ) -> str:
        messages = [{"role": "system", "content": self._build_system_prompt(node)}]

        recent = history[-12:] if len(history) > 12 else history
        for msg in recent:
            if msg.role in ["user", "assistant"]:
                messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": message})
        return await self.llm_client.chat(messages)

    async def chat_stream(
        self,
        node: Node,
        history: List[ConversationMessage],
        message: str
    ) -> AsyncGenerator[str, None]:
        messages = [{"role": "system", "content": self._build_system_prompt(node)}]

        recent = history[-12:] if len(history) > 12 else history
        for msg in recent:
            if msg.role in ["user", "assistant"]:
                messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": message})

        async for chunk in self.llm_client.chat_stream(messages):
            logger.info(f"模型返回stream数据: {chunk}")
            yield chunk


class TaskSummarizer:
    def __init__(self, settings: LLMSettings):
        self.settings = settings
        self.llm_client = LLMClient(settings)

    async def summarize(
        self,
        node: Node,
        request: str,
        steps: List[TaskStep],
        outputs: List[str]
    ) -> str:
        prompt = self._build_prompt(node, request, steps, outputs)
        return await self.llm_client.chat(
            [
                {"role": "system", "content": "你是一个任务执行结果整理助手，只根据给定的任务信息输出简洁结论。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

    def _build_prompt(
        self,
        node: Node,
        request: str,
        steps: List[TaskStep],
        outputs: List[str]
    ) -> str:
        lines = [
            "请根据以下任务执行信息，用中文输出一段简洁、准确的结果总结。",
            "\n要求：",
            "1. 用 2 到 4 句话总结执行结果。",
            "2. 如果输出里包含数值、容量、状态等关键信息，要提炼出来。",
            "3. 不要重复原始日志，不要输出 markdown 列表。",
            "4. 如果结果不完整，要明确指出。",
            f"\n任务请求：{request}",
            f"节点：{describe_node(node)}"
        ]

        if steps:
            lines.append("\n\n执行步骤：")
            for step in steps:
                lines.append(f"- {step.title} [{step.status}]: {step.command}")

        if outputs:
            lines.append("\n\n执行输出：")
            for output in outputs:
                lines.append(f"- {output.strip()}")

        return "\n".join(lines)
