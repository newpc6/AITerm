import asyncio
import json
import logging
import os
import re
from typing import AsyncGenerator, Optional, Dict, Any, List

from app.models import Node, ModelConfig
from app.models.chat import Chat, ChatStatus, Message, MessageType
from app.repositories import INodeRepository, IModelConfigRepository
from app.repositories.chat import ChatRepository
from app.repositories.message import MessageRepository
from app.services.llm import LLMClient, ExecutePlanner, ExecuteRepairer, ExecuteSummarizer, ExecuteStep
from app.services.command import execute_command, describe_node, cancel_command
from app.services.sandbox_manager import SandboxManager, SandboxMode
from app.config import LLMSettings

logger = logging.getLogger("aiterm")


class ExecuteService:
    def __init__(
        self,
        node_repo: INodeRepository,
        model_repo: IModelConfigRepository,
        settings
    ):
        self.node_repo = node_repo
        self.model_repo = model_repo
        self.settings = settings
        self.chat_repo = ChatRepository()
        self.message_repo = MessageRepository()
        self.sandbox = SandboxManager(settings)
        self._running_executions: Dict[str, asyncio.Task] = {}
        self._cancelled_executions: set = set()
        self._execution_steps: Dict[str, List[ExecuteStep]] = {}
        self._step_messages: Dict[str, Dict[int, dict]] = {}

    def _parse_message_metadata(self, content: str) -> dict:
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except:
            pass
        return {}

    async def _save_message(self, chat_id: str, role: str, content: str, msg_type: str = "text", metadata: dict = None):
        if metadata:
            structured_content = {"message": content, **metadata}
            content = json.dumps(structured_content, ensure_ascii=False)

        await self.message_repo.create_message(
            chat_id=chat_id,
            role=role,
            content=content,
            type=msg_type
        )

    async def _save_step_message(self, chat_id: str, index: int, title: str, command: str, status: str = "executing", output: str = ""):
        structured_content = {
            "index": index,
            "title": title,
            "command": command,
            "status": status,
            "output": output
        }
        content = json.dumps(structured_content, ensure_ascii=False)

        msg = await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=content,
            type="step"
        )

        if chat_id not in self._step_messages:
            self._step_messages[chat_id] = {}
        self._step_messages[chat_id][index] = {
            "id": msg.id,
            "index": index,
            "title": title,
            "command": command,
            "status": status,
            "output": output
        }
        return msg

    async def _update_step_output(self, chat_id: str, index: int, output: str, status: str = "completed"):
        if chat_id not in self._step_messages or index not in self._step_messages[chat_id]:
            return

        step_info = self._step_messages[chat_id][index]
        step_info["output"] = output
        step_info["status"] = status

        structured_content = {
            "index": step_info["index"],
            "title": step_info["title"],
            "command": step_info["command"],
            "status": step_info["status"],
            "output": step_info["output"]
        }
        content = json.dumps(structured_content, ensure_ascii=False)

        await self.message_repo.update_message(
            message_id=step_info["id"],
            content=content
        )

    def _is_cancelled(self, chat_id: str) -> bool:
        return chat_id in self._cancelled_executions

    def _check_command_risk(self, command: str) -> tuple:
        if self.sandbox.mode == SandboxMode.HOST:
            return False, ""
        is_dangerous, reason = self.sandbox._check_dangerous_command(command)
        if is_dangerous:
            return True, f"Dangerous command detected: {reason}"
        return False, ""

    def _check_sandbox_path(self, command: str) -> tuple:
        if self.sandbox.mode == SandboxMode.HOST:
            is_dangerous, reason = self.sandbox._check_dangerous_command(
                command)
            if is_dangerous:
                return False, f"Dangerous in host mode: {reason}"
            return True, ""
        return self.sandbox._check_paths_in_command(command)

    def _build_llm_settings(self, model_config: ModelConfig) -> LLMSettings:
        return LLMSettings(
            api_url=model_config.api_url,
            api_key=model_config.api_key,
            model=model_config.model,
            temperature=model_config.temperature,
            extra_params=model_config.extra_params or {},
            sandbox_paths=getattr(self.settings, 'sandbox_paths', []) or []
        )

    async def stop_execution(self, chat_id: str) -> Optional[Chat]:
        chat = await self.chat_repo.get_chat(chat_id)
        if not chat or chat.status in [ChatStatus.COMPLETED.value, ChatStatus.FAILED.value, ChatStatus.CANCELLED.value]:
            return None

        self._cancelled_executions.add(chat_id)
        cancel_command(chat_id)

        if chat_id in self._running_executions:
            self._running_executions[chat_id].cancel()

        await self._save_message(chat_id, "assistant", "执行已停止", "error")

        return await self.chat_repo.update_chat(
            chat_id,
            status=ChatStatus.CANCELLED.value,
            summary="执行已停止"
        )

    async def provide_input(self, chat_id: str, user_input: str) -> Optional[Chat]:
        logger.info(
            f"provide_input called: chat_id={chat_id}, user_input={user_input[:100] if user_input else 'None'}")
        chat = await self.chat_repo.get_chat(chat_id)
        if not chat:
            logger.warning(f"provide_input: chat not found: {chat_id}")
            return None
        if chat.status != ChatStatus.WAITING_INPUT.value:
            logger.warning(
                f"provide_input: unexpected status: {chat.status}, expected {ChatStatus.WAITING_INPUT.value}")
            return None

        await self._save_message(chat_id, "user", user_input, "input_response")

        result = await self.chat_repo.update_chat(
            chat_id,
            status=ChatStatus.ANALYZING.value,
            summary="已收到用户输入，正在重新规划..."
        )
        logger.info(f"provide_input: updated chat status to ANALYZING")
        return result

    async def confirm_execution(self, chat_id: str, approved: bool) -> Optional[Chat]:
        chat = await self.chat_repo.get_chat(chat_id)
        if not chat or chat.status != ChatStatus.WAITING_CONFIRM.value:
            return None

        if approved:
            await self._save_message(chat_id, "user", "确认执行", "approved")
            return await self.chat_repo.update_chat(
                chat_id,
                status=ChatStatus.EXECUTING.value,
                summary="命令已确认，正在执行..."
            )
        else:
            await self._save_message(chat_id, "user", "拒绝执行", "rejected")
            return await self.chat_repo.update_chat(
                chat_id,
                status=ChatStatus.CANCELLED.value,
                summary="执行已取消"
            )

    async def execute(
        self,
        chat_id: str,
        node_id: str,
        message: str,
        model_config: ModelConfig
    ) -> AsyncGenerator[Dict[str, Any], None]:
        node = await self.node_repo.get_node(node_id)
        node_label = describe_node(node) if node else f"节点 {node_id}"

        await self.chat_repo.update_chat(
            chat_id,
            status=ChatStatus.ANALYZING.value,
            summary=f"正在基于节点 {node_label} 生成执行计划"
        )

        llm_settings = self._build_llm_settings(model_config)

        try:
            planner = ExecutePlanner(llm_settings)
            plan = await planner.generate_plan(node, message, [])
        except Exception as e:
            logger.error(f"Execute planning failed: {e}")
            error_msg = f"执行规划失败: {str(e)}"
            await self.chat_repo.update_chat(
                chat_id,
                status=ChatStatus.FAILED.value,
                summary=error_msg
            )
            await self._save_message(chat_id, "assistant", error_msg, "error")
            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "error", "content": error_msg}}
            return

        if self._is_cancelled(chat_id):
            return

        if plan.needs_user_input and plan.input_request:
            await self.chat_repo.update_chat(
                chat_id,
                status=ChatStatus.WAITING_INPUT.value,
                summary=plan.summary
            )

            input_msg = f"需要您的输入：{plan.input_request.question}"
            if plan.input_request.options:
                input_msg += f"\n选项：{', '.join(plan.input_request.options)}"

            await self._save_message(
                chat_id, "assistant", input_msg, "input",
                metadata={
                    "question": plan.input_request.question,
                    "input_type": plan.input_request.input_type,
                    "options": plan.input_request.options,
                    "placeholder": plan.input_request.placeholder
                }
            )
            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "input", "content": input_msg}}
            yield {"event": "conversation.input", "data": {
                "chat_id": chat_id,
                "question": plan.input_request.question,
                "input_type": plan.input_request.input_type,
                "options": plan.input_request.options,
                "placeholder": plan.input_request.placeholder,
                "default_value": plan.input_request.default_value
            }}
            return

        steps = [
            ExecuteStep(
                index=i,
                title=step.title,
                status="pending",
                command=step.command
            )
            for i, step in enumerate(plan.steps)
        ]
        self._execution_steps[chat_id] = steps

        blacklist_risks = []
        for step in steps:
            is_risky, risk_msg = self._check_command_risk(step.command)
            if is_risky:
                blacklist_risks.append(risk_msg)

        if blacklist_risks:
            if plan.risk_reason:
                plan.risk_reason = plan.risk_reason + \
                    "；" + "；".join(blacklist_risks)
            else:
                plan.risk_reason = "；".join(blacklist_risks)

        if plan.risk_reason or plan.requires_confirmation:
            await self.chat_repo.update_chat(
                chat_id,
                status=ChatStatus.WAITING_CONFIRM.value,
                summary=f"{plan.summary} 该计划需要人工确认后才会执行"
            )

            plan_content = "\n".join(
                f"{i+1}. {s.title}: {s.command}" for i, s in enumerate(steps))
            await self._save_message(
                chat_id, "assistant", plan_content, "plan",
                metadata={"steps": [
                    {"index": s.index, "title": s.title, "command": s.command} for s in steps]}
            )
            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "plan", "content": plan_content}}

            confirm_msg = f"该操作需要人工确认后执行。\n{plan_content}"
            if plan.risk_reason:
                confirm_msg += f"\n\n风险提示：{plan.risk_reason}"

            await self._save_message(
                chat_id, "assistant", confirm_msg, "approval",
                metadata={"commands": [
                    s.command for s in steps], "reason": plan.risk_reason or ""}
            )
            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "approval", "content": confirm_msg}}
            return

        await self.chat_repo.update_chat(
            chat_id,
            status=ChatStatus.EXECUTING.value,
            summary=plan.summary
        )

        plan_content = "\n".join(
            f"{i+1}. {s.title}: {s.command}" for i, s in enumerate(steps))
        await self._save_message(
            chat_id, "assistant", plan_content, "plan",
            metadata={"steps": [
                {"index": s.index, "title": s.title, "command": s.command} for s in steps]}
        )
        yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "plan", "content": plan_content}}

        execution_outputs = []

        for index, step in enumerate(steps):
            if self._is_cancelled(chat_id):
                return

            if not step.command.strip():
                continue

            sandbox_ok, sandbox_error = self._check_sandbox_path(step.command)
            if not sandbox_ok:
                step.status = "failed"
                steps[index] = step
                self._execution_steps[chat_id] = steps
                error_msg = f"沙盒路径检查失败：{sandbox_error}"
                await self._save_message(chat_id, "assistant", error_msg, "error")
                yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "error", "content": error_msg}}
                continue

            await self.chat_repo.update_chat(
                chat_id,
                status=ChatStatus.EXECUTING.value,
                summary=f"正在执行第 {index+1}/{len(steps)} 步：{step.title}"
            )

            step.status = "executing"
            steps[index] = step
            self._execution_steps[chat_id] = steps

            start_msg = f"开始执行第 {index+1} 步：{step.title}\n命令：{step.command}"
            await self._save_step_message(
                chat_id, index, step.title, step.command, status="executing"
            )
            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "step", "content": start_msg}}

            result = await execute_command(step.command, task_id=chat_id)
            step_outputs = []
            for stream, content in result.lines:
                if stream == 'stderr':
                    line_text = f"错误: {content}"
                else:
                    line_text = content
                execution_outputs.append(line_text)
                step_outputs.append(line_text)
                yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "output", "content": content}}

            step.result_output = "\n".join(step_outputs)

            if self._is_cancelled(chat_id):
                return

            if result.cancelled:
                step.status = "cancelled"
                cancel_msg = "进程已被用户终止"
                await self._update_step_output(chat_id, index, cancel_msg, status="cancelled")
                yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "output", "content": cancel_msg}}
                continue

            if result.exit_code != 0 or result.error:
                error_text = "命令执行失败"
                if result.timed_out:
                    error_text = "命令执行超时，执行已被终止"
                elif result.error:
                    error_text = f"命令执行失败: {str(result.error)}"

                await self._save_message(chat_id, "assistant", error_text, "error")
                yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "error", "content": error_text}}

                if not result.timed_out and step.repair_count < 2:
                    try:
                        repairer = ExecuteRepairer(llm_settings)
                        repair_result = await repairer.repair(node, message, step, step_outputs, error_text)

                        if repair_result.reason or repair_result.suggestion:
                            analysis = f"失败复盘：原因：{repair_result.reason}"
                            if repair_result.suggestion:
                                analysis += f"；建议：{repair_result.suggestion}"
                            await self._save_message(chat_id, "assistant", analysis, "analysis")
                            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "analysis", "content": analysis}}

                        if repair_result.corrected_command and repair_result.corrected_command != step.command:
                            step.command = repair_result.corrected_command
                            if repair_result.corrected_title:
                                step.title = repair_result.corrected_title
                            step.repair_count += 1
                            step.original_command = step.original_command or step.command
                            step.first_failure_output = step.result_output
                            step.last_error = error_text
                            step.repair_reason = repair_result.reason
                            step.repair_suggestion = repair_result.suggestion
                            step.repaired_command = repair_result.corrected_command

                            retry_msg = f"第 {index+1} 步失败，已自动复盘并修正命令，继续执行：{step.title}\n命令：{step.command}"
                            await self._save_message(
                                chat_id, "assistant", retry_msg, "retry",
                                metadata={
                                    "index": index, "title": step.title, "command": step.command}
                            )
                            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "retry", "content": retry_msg}}

                            result = await execute_command(step.command, task_id=chat_id)
                            step_outputs = []
                            for stream, content in result.lines:
                                if stream == 'stderr':
                                    line_text = f"错误: {content}"
                                else:
                                    line_text = content
                                execution_outputs.append(line_text)
                                step_outputs.append(line_text)
                                yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "output", "content": content}}

                            step.repaired_output = "\n".join(step_outputs)

                            if result.exit_code == 0 and not result.error:
                                success_msg = f"第 {index+1} 步修复后执行成功"
                                await self._update_step_output(chat_id, index, step.repaired_output, status="completed")
                                step.status = "completed"
                                steps[index] = step
                                self._execution_steps[chat_id] = steps
                                continue

                    except Exception as e:
                        logger.error(f"Execute repair failed: {e}")
                        error_msg = f"修复尝试失败: {str(e)}"
                        await self._save_message(chat_id, "assistant", error_msg, "error")
                        yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "error", "content": error_msg}}

                step.status = "failed"
                steps[index] = step
                self._execution_steps[chat_id] = steps

                await self.chat_repo.update_chat(
                    chat_id,
                    status=ChatStatus.FAILED.value,
                    summary=f"第 {index+1} 步执行失败，执行终止"
                )

                yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "error", "content": f"第 {index+1} 步执行失败，执行终止"}}
                return

            await self._update_step_output(chat_id, index, step.result_output, status="completed")
            step.status = "completed"
            steps[index] = step
            self._execution_steps[chat_id] = steps

        try:
            summarizer = ExecuteSummarizer(llm_settings)
            summary = await summarizer.summarize(message, steps, execution_outputs)
        except Exception as e:
            logger.warning(f"Failed to generate summary: {e}")
            summary = f"执行完成，共 {len(steps)} 个步骤"

        await self.chat_repo.update_chat(
            chat_id,
            status=ChatStatus.COMPLETED.value,
            summary=summary
        )

        await self._save_message(chat_id, "assistant", summary, "summary")
        yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "summary", "content": summary}}

        if chat_id in self._execution_steps:
            del self._execution_steps[chat_id]

    async def continue_with_input(
        self,
        chat_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        logger.info(f"continue_with_input called: chat_id={chat_id}")
        chat = await self.chat_repo.get_chat(chat_id)
        if not chat:
            logger.warning(f"continue_with_input: chat not found: {chat_id}")
            return

        if chat.status == ChatStatus.EXECUTING.value:
            logger.info(
                f"continue_with_input: status is EXECUTING, continuing execution")
            async for event in self._continue_execution(chat_id):
                yield event
            return

        if chat.status != ChatStatus.ANALYZING.value:
            logger.warning(
                f"continue_with_input: unexpected status: {chat.status}, expected ANALYZING or EXECUTING")
            return

        model_config = await self._get_model_config(chat.model_id)
        if not model_config:
            error_msg = "未配置模型，请先在设置页添加模型配置"
            logger.error(f"continue_with_input: {error_msg}")
            await self.chat_repo.update_chat(
                chat_id,
                status=ChatStatus.FAILED.value,
                summary=error_msg
            )
            await self._save_message(chat_id, "assistant", error_msg, "error")
            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "error", "content": error_msg}}
            return

        messages = await self.message_repo.list_messages(chat_id, 1, 50)
        user_input = ""
        original_request = ""

        for msg in reversed(messages):
            if msg.type == "input_response":
                user_input = msg.content
            elif msg.role == "user" and msg.type == "text":
                original_request = msg.content
                break

        logger.info(
            f"continue_with_input: original_request={original_request[:50] if original_request else 'None'}, user_input={user_input[:50] if user_input else 'None'}")

        if not original_request:
            error_msg = "无法找到原始请求"
            logger.error(f"continue_with_input: {error_msg}")
            await self.chat_repo.update_chat(
                chat_id,
                status=ChatStatus.FAILED.value,
                summary=error_msg
            )
            await self._save_message(chat_id, "assistant", error_msg, "error")
            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "error", "content": error_msg}}
            return

        enhanced_request = f"{original_request}\n\n用户补充信息：{user_input}" if user_input else original_request
        logger.info(
            f"continue_with_input: enhanced_request={enhanced_request[:100]}...")

        node = await self.node_repo.get_node(chat.node_id)
        llm_settings = self._build_llm_settings(model_config)

        try:
            logger.info(f"continue_with_input: calling planner.generate_plan")
            planner = ExecutePlanner(llm_settings)
            plan = await planner.generate_plan(node, enhanced_request, [])
            logger.info(
                f"continue_with_input: plan generated, steps={len(plan.steps) if plan else 0}")
        except Exception as e:
            logger.error(f"Execute re-planning failed: {e}", exc_info=True)
            error_msg = f"重新规划失败: {str(e)}"
            await self.chat_repo.update_chat(
                chat_id,
                status=ChatStatus.FAILED.value,
                summary=error_msg
            )
            await self._save_message(chat_id, "assistant", error_msg, "error")
            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "error", "content": error_msg}}
            return

        logger.info(f"continue_with_input: calling _execute_plan")
        async for event in self._execute_plan(chat_id, plan, model_config, node, enhanced_request):
            yield event

    async def _continue_execution(
        self,
        chat_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        chat = await self.chat_repo.get_chat(chat_id)
        if not chat:
            return

        steps = self._execution_steps.get(chat_id, [])
        if not steps:
            messages = await self.message_repo.list_messages(chat_id, 1, 50)
            for msg in reversed(messages):
                if msg.type == "plan":
                    metadata = self._parse_message_metadata(msg.content)
                    if metadata and "steps" in metadata:
                        steps = [
                            ExecuteStep(
                                index=s.get("index", i),
                                title=s.get("title", ""),
                                status="pending",
                                command=s.get("command", "")
                            )
                            for i, s in enumerate(metadata.get("steps", []))
                        ]
                        self._execution_steps[chat_id] = steps
                        logger.info(
                            f"_continue_execution: restored {len(steps)} steps from message")
                        break

        if not steps:
            error_msg = "未找到执行计划"
            logger.error(f"_continue_execution: {error_msg}")
            await self.chat_repo.update_chat(
                chat_id,
                status=ChatStatus.FAILED.value,
                summary=error_msg
            )
            await self._save_message(chat_id, "assistant", error_msg, "error")
            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "error", "content": error_msg}}
            return

        model_config = await self._get_model_config(chat.model_id)
        if not model_config:
            error_msg = "未配置模型"
            logger.error(f"_continue_execution: {error_msg}")
            await self.chat_repo.update_chat(
                chat_id,
                status=ChatStatus.FAILED.value,
                summary=error_msg
            )
            await self._save_message(chat_id, "assistant", error_msg, "error")
            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "error", "content": error_msg}}
            return

        node = await self.node_repo.get_node(chat.node_id)
        llm_settings = self._build_llm_settings(model_config)

        messages = await self.message_repo.list_messages(chat_id, 1, 50)
        original_request = ""
        for msg in reversed(messages):
            if msg.role == "user" and msg.type == "text":
                original_request = msg.content
                break

        execution_outputs = []
        for index, step in enumerate(steps):
            if self._is_cancelled(chat_id):
                return

            if step.status != "pending" or not step.command.strip():
                continue

            await self.chat_repo.update_chat(
                chat_id,
                status=ChatStatus.EXECUTING.value,
                summary=f"正在执行第 {index+1}/{len(steps)} 步：{step.title}"
            )

            step.status = "executing"
            steps[index] = step
            self._execution_steps[chat_id] = steps

            start_msg = f"开始执行第 {index+1} 步：{step.title}\n命令：{step.command}"
            await self._save_step_message(
                chat_id, index, step.title, step.command, status="executing"
            )
            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "step", "content": start_msg}}

            result = await execute_command(step.command, task_id=chat_id)
            step_outputs = []
            for stream, content in result.lines:
                if stream == 'stderr':
                    line_text = f"错误: {content}"
                else:
                    line_text = content
                execution_outputs.append(line_text)
                step_outputs.append(line_text)
                yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "output", "content": content}}

            step.result_output = "\n".join(step_outputs)

            if result.exit_code != 0 or result.error:
                error_text = f"命令执行失败: {result.error or '未知错误'}"
                await self._save_message(chat_id, "assistant", error_text, "error")
                yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "error", "content": error_text}}

                step.status = "failed"
                steps[index] = step
                self._execution_steps[chat_id] = steps

                await self.chat_repo.update_chat(
                    chat_id,
                    status=ChatStatus.FAILED.value,
                    summary=f"第 {index+1} 步执行失败"
                )
                return

            await self._update_step_output(chat_id, index, step.result_output, status="completed")
            step.status = "completed"
            steps[index] = step
            self._execution_steps[chat_id] = steps

        try:
            summarizer = ExecuteSummarizer(llm_settings)
            summary = await summarizer.summarize(original_request, steps, execution_outputs)
        except Exception as e:
            logger.warning(f"Failed to generate summary: {e}")
            summary = f"执行完成，共 {len(steps)} 个步骤"

        await self.chat_repo.update_chat(
            chat_id,
            status=ChatStatus.COMPLETED.value,
            summary=summary
        )

        await self._save_message(chat_id, "assistant", summary, "summary")
        yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "summary", "content": summary}}

        if chat_id in self._execution_steps:
            del self._execution_steps[chat_id]

    async def _get_model_config(self, model_id: str) -> Optional[ModelConfig]:
        if not model_id:
            settings = self.settings
            if hasattr(settings, 'default_model_id') and settings.default_model_id:
                return await self.model_repo.get_model(settings.default_model_id)
            return None
        return await self.model_repo.get_model(model_id)

    async def _execute_plan(self, chat_id: str, plan, model_config: ModelConfig, node: Node, message: str) -> AsyncGenerator[Dict[str, Any], None]:
        steps = [
            ExecuteStep(
                index=i,
                title=step.title,
                status="pending",
                command=step.command
            )
            for i, step in enumerate(plan.steps)
        ]
        self._execution_steps[chat_id] = steps

        if plan.risk_reason or plan.requires_confirmation:
            await self.chat_repo.update_chat(
                chat_id,
                status=ChatStatus.WAITING_CONFIRM.value,
                summary=f"{plan.summary} 该计划需要人工确认后才会执行"
            )

            plan_content = "\n".join(
                f"{i+1}. {s.title}: {s.command}" for i, s in enumerate(steps))
            await self._save_message(
                chat_id, "assistant", plan_content, "plan",
                metadata={"steps": [
                    {"index": s.index, "title": s.title, "command": s.command} for s in steps]}
            )
            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "plan", "content": plan_content}}

            confirm_msg = f"该操作需要人工确认后执行。\n{plan_content}"
            if plan.risk_reason:
                confirm_msg += f"\n\n风险提示：{plan.risk_reason}"

            await self._save_message(
                chat_id, "assistant", confirm_msg, "approval",
                metadata={"commands": [
                    s.command for s in steps], "reason": plan.risk_reason or ""}
            )
            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "approval", "content": confirm_msg}}
            return

        await self.chat_repo.update_chat(
            chat_id,
            status=ChatStatus.EXECUTING.value,
            summary=plan.summary
        )

        plan_content = "\n".join(
            f"{i+1}. {s.title}: {s.command}" for i, s in enumerate(steps))
        await self._save_message(
            chat_id, "assistant", plan_content, "plan",
            metadata={"steps": [
                {"index": s.index, "title": s.title, "command": s.command} for s in steps]}
        )
        yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "plan", "content": plan_content}}

        llm_settings = self._build_llm_settings(model_config)
        execution_outputs = []

        for index, step in enumerate(steps):
            if self._is_cancelled(chat_id):
                return

            if not step.command.strip():
                continue

            await self.chat_repo.update_chat(
                chat_id,
                status=ChatStatus.EXECUTING.value,
                summary=f"正在执行第 {index+1}/{len(steps)} 步：{step.title}"
            )

            step.status = "executing"
            steps[index] = step
            self._execution_steps[chat_id] = steps

            start_msg = f"开始执行第 {index+1} 步：{step.title}\n命令：{step.command}"
            await self._save_message(
                chat_id, "assistant", start_msg, "step",
                metadata={"index": index, "title": step.title,
                          "command": step.command, "status": "executing"}
            )
            yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "step", "content": start_msg}}

            result = await execute_command(step.command, task_id=chat_id)
            step_outputs = []
            for stream, content in result.lines:
                if stream == 'stderr':
                    line_text = f"错误: {content}"
                else:
                    line_text = content
                execution_outputs.append(line_text)
                step_outputs.append(line_text)
                await self._save_message(
                    chat_id, "assistant", line_text, "output",
                    metadata={"command": step.command,
                              "output": content, "stream": stream}
                )
                yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "output", "content": content}}

            step.result_output = "\n".join(step_outputs)

            if result.exit_code != 0 or result.error:
                error_text = f"命令执行失败: {result.error or '未知错误'}"
                await self._save_message(chat_id, "assistant", error_text, "error")
                yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "error", "content": error_text}}

                step.status = "failed"
                steps[index] = step
                self._execution_steps[chat_id] = steps

                await self.chat_repo.update_chat(
                    chat_id,
                    status=ChatStatus.FAILED.value,
                    summary=f"第 {index+1} 步执行失败"
                )
                return

            step.status = "completed"
            steps[index] = step
            self._execution_steps[chat_id] = steps

        try:
            summarizer = ExecuteSummarizer(llm_settings)
            summary = await summarizer.summarize(message, steps, execution_outputs)
        except Exception as e:
            logger.warning(f"Failed to generate summary: {e}")
            summary = f"执行完成，共 {len(steps)} 个步骤"

        await self.chat_repo.update_chat(
            chat_id,
            status=ChatStatus.COMPLETED.value,
            summary=summary
        )

        await self._save_message(chat_id, "assistant", summary, "summary")
        yield {"event": "conversation.message", "data": {"chat_id": chat_id, "type": "summary", "content": summary}}

        if chat_id in self._execution_steps:
            del self._execution_steps[chat_id]
