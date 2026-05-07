import json
import re
from typing import List, Optional, Dict, Any, AsyncGenerator, Union, TypedDict
from datetime import datetime

from app.config import LLMSettings
from app.models import (
    Node,
    ModelConfig
)
from app.models.chat import Message
from app.services.command import detect_platform, describe_node
from app.services.llm_providers.factory import create_llm_client
import logging

logger = logging.getLogger("aiterm")


class StreamChunk(TypedDict):
    type: str
    content: str


class ExecuteStep:
    def __init__(self, index: int = 0, title: str = "", status: str = "pending", command: str = "", result_output: str = None, repair_count: int = 0, original_command: str = None, first_failure_output: str = None, repaired_output: str = None, last_error: str = None, repair_reason: str = None, repair_suggestion: str = None, repaired_command: str = None):
        self.index = index
        self.title = title
        self.status = status
        self.command = command
        self.result_output = result_output
        self.repair_count = repair_count
        self.original_command = original_command
        self.first_failure_output = first_failure_output
        self.repaired_output = repaired_output
        self.last_error = last_error
        self.repair_reason = repair_reason
        self.repair_suggestion = repair_suggestion
        self.repaired_command = repaired_command


class ExecutePlanStep:
    def __init__(self, title: str = "", command: str = ""):
        self.title = title
        self.command = command


class UserInputRequest:
    def __init__(self, question: str = "", input_type: str = "text", options: List[str] = None, placeholder: str = "", default_value: str = ""):
        self.question = question
        self.input_type = input_type
        self.options = options or []
        self.placeholder = placeholder
        self.default_value = default_value


class ExecutePlanResult:
    def __init__(self, title: str = "", summary: str = "", requires_confirmation: bool = False, risk_reason: str = "", needs_user_input: bool = False, input_request: Optional[UserInputRequest] = None, steps: List[ExecutePlanStep] = None):
        self.title = title
        self.summary = summary
        self.requires_confirmation = requires_confirmation
        self.risk_reason = risk_reason
        self.needs_user_input = needs_user_input
        self.input_request = input_request
        self.steps = steps or []


class ExecuteFailureRepairResult:
    def __init__(self, reason: str = "", suggestion: str = "", corrected_title: str = "", corrected_command: str = ""):
        self.reason = reason
        self.suggestion = suggestion
        self.corrected_title = corrected_title
        self.corrected_command = corrected_command


class LLMClient:
    def __init__(self, settings: Union[LLMSettings, ModelConfig], debug_logging: bool = False):
        self._provider = create_llm_client(
            settings, debug_logging=debug_logging)
        self.settings = settings
        self.timeout = 90.0
        self.debug_logging = debug_logging

    @property
    def api_url(self) -> str:
        return self._provider.api_url

    @property
    def api_key(self) -> str:
        return self._provider.api_key

    @property
    def model(self) -> str:
        return self._provider.model

    @property
    def temperature(self) -> float:
        return self._provider.temperature

    @property
    def extra_params(self) -> Dict[str, Any]:
        return self._provider.extra_params

    @property
    def extra_body(self) -> Dict[str, Any]:
        return self._provider.extra_body

    @property
    def extra_headers(self) -> Dict[str, str]:
        return self._provider.extra_headers

    def _build_chat_url(self) -> str:
        return self._provider._get_chat_url()

    def _get_headers(self) -> Dict[str, str]:
        return self._provider._get_headers()

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        stream: bool = True
    ) -> str:
        return await self._provider.chat(messages, temperature, stream)

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        async for chunk in self._provider.chat_stream(messages, temperature):
            yield chunk

    async def chat_with_tools_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: Optional[float] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        async for chunk in self._provider.chat_with_tools_stream(messages, tools, temperature):
            yield chunk


class ExecutePlanner:
    def __init__(self, settings: LLMSettings):
        self.settings = settings
        self.llm_client = LLMClient(settings)

    def _build_system_prompt(self, node: Node, request: str) -> str:
        template = self.settings.execution_planner_prompt or "你是一个执行规划器，请将用户请求转换为可执行操作计划。"
        command_rules = self._build_command_rules()
        sandbox_info = self._build_sandbox_info()
        node_desc = describe_node(node)
        sandbox_paths = self.settings.sandbox_paths or []
        sandbox_paths_str = ", ".join(
            sandbox_paths) if sandbox_paths else "未配置"

        prompt = template.replace("{{node_description}}", node_desc)
        prompt = prompt.replace("{{user_request}}", request)
        prompt = prompt.replace("{{sandbox_paths}}", sandbox_paths_str)
        prompt += command_rules
        prompt += sandbox_info
        prompt += """

你必须只返回 JSON，不要输出 markdown，不要输出解释。JSON 结构如下：

1. 正常执行计划：
{"title":"操作标题","summary":"操作摘要","requires_confirmation":false,"risk_reason":"","needs_user_input":false,"steps":[{"title":"步骤标题","command":"具体命令"}]}

2. 需要用户补充信息时（如缺少下载地址、文件路径等关键信息）：
{"title":"操作标题","summary":"需要用户补充信息","requires_confirmation":false,"risk_reason":"","needs_user_input":true,"input_request":{"question":"请提供下载地址","input_type":"text","options":[],"placeholder":"输入下载地址","default_value":""},"steps":[]}

3. 需要用户选择方案时（有多种实现方式）：
{"title":"操作标题","summary":"请选择实现方案","requires_confirmation":false,"risk_reason":"","needs_user_input":true,"input_request":{"question":"请选择下载方式","input_type":"select","options":["直接下载","使用代理下载","使用镜像站"],"placeholder":"","default_value":"直接下载"},"steps":[]}

input_type 可选值：text（文本输入）、select（单选）、multiselect（多选）
如果信息充足，直接生成 steps；如果信息不足或需要用户选择，设置 needs_user_input 为 true 并填写 input_request。"""

        return prompt

    def _build_user_prompt(
        self,
        node: Node,
        request: str,
        history: List[Dict[str, Any]]
    ) -> str:
        template = self.settings.execution_planner_user_prompt or "请基于以下用户请求生成执行计划。"
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

    def _build_history_text(self, history: List[Union[Dict[str, Any], Message]]) -> str:
        if not history:
            return ""

        recent = history[-6:] if len(history) > 6 else history
        lines = ["\n\n最近对话上下文："]
        for msg in recent:
            if isinstance(msg, Message):
                role = msg.role
                content = msg.content
            else:
                role = msg.get("role", "")
                content = msg.get("content", "")
            if role in ["user", "assistant"]:
                lines.append(f"- {role}: {content.strip()}")

        return "\n".join(lines)

    def _build_platform_prompt(self, node: Node) -> tuple:
        platform = detect_platform(node)
        if platform == "windows":
            return "Windows", self.settings.execution_windows_tool_prompt
        elif platform == "linux":
            return "Linux", self.settings.execution_linux_tool_prompt
        elif platform == "macos":
            return "macOS", self.settings.execution_mac_tool_prompt
        return "未知", ""

    def _build_command_rules(self) -> str:
        blacklist = self.settings.execution_command_blacklist or []
        whitelist = self.settings.execution_command_whitelist or []

        if not blacklist and not whitelist:
            return ""

        rules = []
        if blacklist:
            rules.append(f"- 以下命令片段命中后会强制人工确认，请尽量避免误触：{'、'.join(blacklist)}")
        if whitelist:
            rules.append(f"- 以下命令片段属于白名单，可在生成命令时参考：{'、'.join(whitelist)}")

        template = self.settings.execution_command_rules_prompt or "\n\n命令风控规则：{{command_rules}}"
        return "\n\n" + template.replace("{{command_rules}}", "\n".join(rules))

    def _build_sandbox_info(self) -> str:
        sandbox_paths = self.settings.sandbox_paths or []

        if not sandbox_paths:
            return ""

        paths_text = "\n".join(f"  - {path}" for path in sandbox_paths)

        default_rules = """【沙盒路径限制】
所有文件读写操作必须在以下沙盒路径内进行：
{{paths_text}}

重要规则：
1. 创建、写入、修改文件时，路径必须在上述沙盒目录内
2. 不要操作沙盒路径之外的文件，特别是系统关键文件（如 main.py、配置文件等）
3. 如果用户请求的操作需要访问沙盒外的路径，请提示用户确认或要求用户提供沙盒内的路径
4. 优先使用沙盒路径下的子目录来组织文件"""

        template = self.settings.sandbox_rules_prompt or default_rules
        return "\n\n" + template.replace("{{paths_text}}", paths_text)

    async def generate_plan(
        self,
        node: Node,
        request: str,
        history: List[Dict[str, Any]]
    ) -> ExecutePlanResult:
        messages = [
            {"role": "system", "content": self._build_system_prompt(
                node, request)},
            {"role": "user", "content": self._build_user_prompt(
                node, request, history)}
        ]

        response = await self.llm_client.chat(messages, temperature=0.2)
        return self._parse_plan(response)

    def _parse_plan(self, raw: str) -> ExecutePlanResult:
        logger.info(f"Parsing plan from response: {raw[:200]}...")
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
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode failed, attempting repair: {e}")
            repaired = self._repair_json(cleaned)
            data = json.loads(repaired)

        steps = []
        for step in data.get("steps", []):
            command = step.get("command", "").strip()
            if command:
                steps.append(ExecutePlanStep(
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

        result = ExecutePlanResult(
            title=data.get("title", "").strip() or "模型生成任务",
            summary=data.get("summary", "").strip() or "模型已生成执行计划。",
            requires_confirmation=data.get("requires_confirmation", False),
            risk_reason=data.get("risk_reason", "").strip(),
            needs_user_input=data.get("needs_user_input", False),
            input_request=input_request,
            steps=steps
        )
        logger.info(
            f"Plan parsed successfully: title={result.title}, needs_user_input={result.needs_user_input}")
        return result

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


class ExecuteRepairer:
    def __init__(self, settings: LLMSettings):
        self.settings = settings
        self.llm_client = LLMClient(settings)

    async def repair(
        self,
        node: Node,
        request: str,
        step: ExecuteStep,
        outputs: List[str],
        failure_text: str
    ) -> ExecuteFailureRepairResult:
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
        step: ExecuteStep,
        outputs: List[str],
        failure_text: str
    ) -> str:
        template = self.settings.execution_failure_repair_prompt or "请分析以下执行操作失败信息。"
        node_desc = describe_node(node)

        prompt = template.replace("{{node_description}}", node_desc)
        prompt = prompt.replace("{{user_request}}", request)
        prompt = prompt.replace("{{step_title}}", step.title)
        prompt = prompt.replace("{{failed_command}}", step.command)
        prompt = prompt.replace("{{execution_output}}", "\n".join(
            outputs) if outputs else "无输出")
        prompt = prompt.replace("{{failure_text}}", failure_text)

        return prompt

    def _parse_result(self, raw: str, step: ExecuteStep) -> ExecuteFailureRepairResult:
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
            return ExecuteFailureRepairResult()

        result = ExecuteFailureRepairResult(
            reason=data.get("reason", "").strip(),
            suggestion=data.get("suggestion", "").strip(),
            corrected_title=data.get("corrected_title", "").strip(),
            corrected_command=data.get("corrected_command", "").strip()
        )

        if not result.corrected_command:
            result.corrected_command = self._infer_command(raw, step)

        return result

    def _infer_command(self, text: str, step: ExecuteStep) -> str:
        pattern = r"`([^`\r\n]+)`"
        matches = re.findall(pattern, text)

        for match in matches:
            candidate = match.strip().strip("\"'")
            if candidate and not any(kw in candidate.lower() for kw in ["json", "markdown", "reason", "suggestion"]):
                if len(candidate) <= 300:
                    return candidate

        return ""


class ChatService:
    def __init__(self, settings: Union[LLMSettings, ModelConfig], chat_system_prompt: str = "", chat_history_limit: int = 12):
        self.settings = settings
        self.chat_system_prompt = chat_system_prompt
        self.chat_history_limit = chat_history_limit
        self.llm_client = LLMClient(settings)

    def _build_system_prompt(self, node: Node) -> str:
        template = self.chat_system_prompt or "你是一个中文 AI 助手，请直接回答用户问题，保持简洁、准确。"
        node_desc = describe_node(node)
        return template.replace("{{node_description}}", node_desc)

    async def chat(
        self,
        node: Node,
        history: List[Dict[str, Any]],
        message: str
    ) -> str:
        messages = [
            {"role": "system", "content": self._build_system_prompt(node)}]

        limit = self.chat_history_limit
        recent = history[-limit:] if len(history) > limit else history
        for msg in recent:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ["user", "assistant"]:
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": message})
        return await self.llm_client.chat(messages)

    async def chat_stream(
        self,
        node: Node,
        history: List[Dict[str, Any]],
        message: str
    ) -> AsyncGenerator[StreamChunk, None]:
        messages = [
            {"role": "system", "content": self._build_system_prompt(node)}]

        limit = self.chat_history_limit
        recent = history[-limit:] if len(history) > limit else history
        for msg in recent:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ["user", "assistant"]:
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": message})

        logger.info(
            f"ChatService.chat_stream: Starting with {len(messages)} messages (history_limit={limit})")
        logger.info(
            f"ChatService.chat_stream: System prompt: {messages[0]['content'][:100]}...")
        logger.info(
            f"ChatService.chat_stream: User message: {message[:100]}...")

        chunk_count = 0
        usage = {}
        async for chunk in self.llm_client.chat_stream(messages):
            chunk_count += 1
            if chunk.get("type") == "usage":
                usage = chunk.get("usage", {})
                continue
            yield chunk

        if usage:
            yield {"type": "usage", "usage": usage}

        logger.info(
            f"ChatService.chat_stream: Finished with {chunk_count} chunks")


class ExecuteSummarizer:
    def __init__(self, settings: LLMSettings):
        self.settings = settings
        self.llm_client = LLMClient(settings)

    async def summarize(
        self,
        node: Node,
        request: str,
        steps: List[ExecuteStep],
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
        steps: List[ExecuteStep],
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
