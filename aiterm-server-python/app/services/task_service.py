import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, AsyncGenerator, Tuple

from app.models import (
    Task, TaskStep, Node, ConversationMessage, ModelConfig,
    TaskStatus, TaskStepStatus, TaskPlanResult
)
from app.repositories import ITaskRepository, INodeRepository, IConversationRepository, IModelConfigRepository
from app.services.command import execute_command, describe_node, cancel_command
from app.services.llm import TaskPlanner, TaskRepairer, TaskSummarizer
from app.config import LLMSettings

logger = logging.getLogger("aiterm.task_service")


class TaskService:
    def __init__(
        self,
        task_repo: ITaskRepository,
        node_repo: INodeRepository,
        conversation_repo: IConversationRepository,
        model_repo: IModelConfigRepository,
        settings
    ):
        self.task_repo = task_repo
        self.node_repo = node_repo
        self.conversation_repo = conversation_repo
        self.model_repo = model_repo
        self.settings = settings
        self._counter = 1
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._cancelled_tasks: set = set()

    def _next_id(self) -> str:
        current = self._counter
        self._counter += 1
        return str(current)

    async def list_tasks(self, page: int = 1, page_size: int = 20) -> Tuple[List[Task], int]:
        return await self.task_repo.list_tasks(page, page_size)

    async def get_task(self, task_id: str) -> Optional[Task]:
        return await self.task_repo.get_task(task_id)

    async def delete_task(self, task_id: str) -> bool:
        if task_id in self._running_tasks:
            self._cancelled_tasks.add(task_id)
            self._running_tasks[task_id].cancel()
        return await self.task_repo.delete_task(task_id)

    async def create_task(
        self,
        conversation_id: str,
        node_id: str,
        request: str,
        model_id: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Task:
        now = datetime.utcnow().isoformat()
        node = await self.node_repo.get_node(node_id)
        node_label = describe_node(node) if node else f"节点 {node_id}"

        task = Task(
            id=self._next_id(),
            title=f"任务: {request[:50]}",
            status=TaskStatus.PENDING,
            progress=0,
            conversation_id=conversation_id,
            node_id=node_id,
            model_id=model_id,
            model_name=model_name,
            request=request,
            summary=f"任务已创建，等待模型基于节点 {node_label} 生成执行计划。",
            steps=[],
            created_at=now,
            updated_at=now
        )
        return await self.task_repo.create_task(task)

    async def confirm_task(self, task_id: str, approved: bool) -> Optional[Task]:
        task = await self.task_repo.get_task(task_id)
        if not task or task.status != TaskStatus.WAITING_CONFIRM:
            return None

        now = datetime.utcnow().isoformat()
        if approved:
            task.status = TaskStatus.PENDING
            task.progress = max(task.progress, 45)
            task.summary = "命令已确认，等待执行流启动。"
            for step in task.steps:
                if step.status == TaskStepStatus.WAITING_CONFIRM:
                    step.status = TaskStepStatus.PENDING
        else:
            task.status = TaskStatus.CANCELLED
            task.progress = 100
            task.summary = "任务已取消，待确认命令未执行。"
            for step in task.steps:
                if step.status in [TaskStepStatus.WAITING_CONFIRM, TaskStepStatus.PENDING]:
                    step.status = TaskStepStatus.CANCELLED

        task.updated_at = now
        return await self.task_repo.update_task(task_id, task)

    async def stop_task(self, task_id: str) -> Optional[Task]:
        task = await self.task_repo.get_task(task_id)
        if not task or task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return None

        self._cancelled_tasks.add(task_id)
        cancel_command(task_id)

        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()

        now = datetime.utcnow().isoformat()
        task.status = TaskStatus.CANCELLED
        task.progress = 100
        task.summary = "任务已停止。"
        task.updated_at = now

        for step in task.steps:
            if step.status not in [TaskStepStatus.COMPLETED, TaskStepStatus.FAILED]:
                step.status = TaskStepStatus.CANCELLED

        return await self.task_repo.update_task(task_id, task)

    async def restart_task(self, task_id: str) -> Optional[Task]:
        task = await self.task_repo.get_task(task_id)
        if not task:
            return None

        if task_id in self._running_tasks:
            return None

        if task.status not in [TaskStatus.WAITING_CONFIRM, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return None

        node = await self.node_repo.get_node(task.node_id)
        node_label = describe_node(node) if node else f"节点 {task.node_id}"

        self._cancelled_tasks.discard(task_id)

        now = datetime.utcnow().isoformat()
        task.status = TaskStatus.PENDING
        task.progress = 0
        task.pending_command = None
        task.risk_reason = None
        task.summary = f"任务已重新启动，等待模型基于节点 {node_label} 生成执行计划。"
        task.steps = []
        task.updated_at = now

        return await self.task_repo.update_task(task_id, task)

    async def provide_input(self, task_id: str, user_input: str) -> Optional[Task]:
        task = await self.task_repo.get_task(task_id)
        if not task or task.status != TaskStatus.WAITING_INPUT:
            return None

        now = datetime.utcnow().isoformat()
        task.user_input = user_input
        task.status = TaskStatus.PENDING
        task.progress = 45
        task.summary = f"已收到用户输入，正在重新规划任务..."
        task.updated_at = now
        await self.task_repo.update_task(task_id, task)

        return task

    async def continue_with_input(
        self,
        task_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        task = await self.task_repo.get_task(task_id)
        if not task or task.status != TaskStatus.PENDING or not task.user_input:
            return

        model_config = await self._get_model_config(task)
        if not model_config:
            now = datetime.utcnow().isoformat()
            task.status = TaskStatus.FAILED
            task.progress = 100
            task.summary = "未配置模型，请先在设置页添加模型配置。"
            task.updated_at = now
            await self.task_repo.update_task(task_id, task)
            yield {"event": "task.status", "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}}
            return

        llm_settings = self._build_llm_settings(model_config)
        node = await self.node_repo.get_node(task.node_id)
        node_label = describe_node(node) if node else f"节点 {task.node_id}"

        now = datetime.utcnow().isoformat()
        task.status = TaskStatus.ANALYZING
        task.progress = 50
        task.summary = "正在根据用户输入重新规划任务..."
        task.updated_at = now
        await self.task_repo.update_task(task_id, task)

        yield {"event": "task.status", "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}}

        if self._is_cancelled(task_id):
            return

        enhanced_request = f"{task.request}\n\n用户补充信息：{task.user_input}"

        try:
            planner = TaskPlanner(llm_settings)
            plan = await planner.generate_plan(node, enhanced_request, [])
        except Exception as e:
            logger.error(f"Task re-planning failed: {e}")
            now = datetime.utcnow().isoformat()
            task.status = TaskStatus.FAILED
            task.progress = 100
            task.summary = f"任务重新规划失败：{str(e)}"
            task.updated_at = now
            await self.task_repo.update_task(task_id, task)
            yield {"event": "task.status", "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}}
            yield {"event": "task.output", "data": {"task_id": task_id, "stream": "stderr", "content": f"任务重新规划失败: {str(e)}"}}
            return

        if self._is_cancelled(task_id):
            return

        if plan.needs_user_input and plan.input_request:
            now = datetime.utcnow().isoformat()
            task.title = plan.title or task.title
            task.summary = plan.summary
            task.status = TaskStatus.WAITING_INPUT
            task.progress = 40
            task.input_question = plan.input_request.question
            task.input_type = plan.input_request.input_type
            task.input_options = plan.input_request.options
            task.input_placeholder = plan.input_request.placeholder
            task.user_input = None
            task.updated_at = now
            await self.task_repo.update_task(task_id, task)

            yield {"event": "task.status", "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}}

            input_msg = f"需要您的输入：{plan.input_request.question}"
            if plan.input_request.options:
                input_msg += f"\n选项：{', '.join(plan.input_request.options)}"
            await self.conversation_repo.append_message(ConversationMessage(
                id="0", conversation_id=task.conversation_id, role="assistant",
                content=input_msg, created_at=datetime.utcnow().isoformat()
            ))
            yield {"event": "task.output", "data": {"task_id": task_id, "stream": "input.request", "content": input_msg}}
            yield {"event": "task.input", "data": {
                "task_id": task_id,
                "question": plan.input_request.question,
                "input_type": plan.input_request.input_type,
                "options": plan.input_request.options,
                "placeholder": plan.input_request.placeholder,
                "default_value": plan.input_request.default_value
            }}
            return

        steps = [
            TaskStep(
                index=i,
                title=step.title,
                status=TaskStepStatus.PENDING,
                command=step.command
            )
            for i, step in enumerate(plan.steps)
        ]

        pending_preview = "\n".join(f"{i+1}. {s.title}: {s.command}" for i, s in enumerate(plan.steps))

        now = datetime.utcnow().isoformat()
        task.title = plan.title or task.title
        task.pending_command = pending_preview
        task.risk_reason = plan.risk_reason
        task.summary = plan.summary
        task.steps = steps
        task.progress = 55
        task.updated_at = now

        if plan.risk_reason or plan.requires_confirmation:
            task.status = TaskStatus.WAITING_CONFIRM
            task.summary = f"{task.summary} 该计划需要人工确认后才会执行。"
            for step in task.steps:
                step.status = TaskStepStatus.WAITING_CONFIRM
        else:
            task.status = TaskStatus.EXECUTING

        await self.task_repo.update_task(task_id, task)

        yield {"event": "task.status", "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}}

        planned_msg = f"已根据用户输入生成 {len(task.steps)} 个执行步骤。"
        await self.conversation_repo.append_message(ConversationMessage(
            id="0", conversation_id=task.conversation_id, role="assistant",
            content=planned_msg, created_at=datetime.utcnow().isoformat()
        ))
        yield {"event": "task.output", "data": {"task_id": task_id, "stream": "plan.info", "content": planned_msg}}

        if task.status == TaskStatus.WAITING_CONFIRM:
            confirm_msg = f"该任务需要人工确认后执行。\n{pending_preview}"
            yield {"event": "task.output", "data": {"task_id": task_id, "stream": "approval", "content": confirm_msg}}
            return

        execution_outputs = []

        for index, step in enumerate(task.steps):
            if self._is_cancelled(task_id):
                return

            if not step.command.strip():
                continue

            now = datetime.utcnow().isoformat()
            task.status = TaskStatus.EXECUTING
            task.progress = 55 + int((index / len(task.steps)) * 35)
            task.summary = f"正在执行第 {index+1}/{len(task.steps)} 步：{step.title}"
            task.updated_at = now
            step.status = TaskStepStatus.EXECUTING
            task.steps[index] = step
            await self.task_repo.update_task(task_id, task)

            yield {"event": "task.status", "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}}

            start_msg = f"开始执行第 {index+1} 步：{step.title}\n命令：{step.command}"
            await self.conversation_repo.append_message(ConversationMessage(
                id="0", conversation_id=task.conversation_id, role="assistant",
                content=start_msg, created_at=datetime.utcnow().isoformat()
            ))
            yield {"event": "task.output", "data": {"task_id": task_id, "stream": "step.start", "content": start_msg}}

            result = await execute_command(step.command, task_id=task_id)
            step_outputs = []
            for stream, content in result.lines:
                line_text = f"[{stream}] {content}"
                execution_outputs.append(line_text)
                step_outputs.append(line_text)
                await self.conversation_repo.append_message(ConversationMessage(
                    id="0", conversation_id=task.conversation_id, role="assistant",
                    content=line_text, created_at=datetime.utcnow().isoformat()
                ))
                yield {"event": "task.output", "data": {"task_id": task_id, "stream": stream, "content": content}}

            step.result_output = "\n".join(step_outputs)

            if self._is_cancelled(task_id):
                return

            if result.cancelled:
                step.status = TaskStepStatus.CANCELLED
                cancel_msg = "进程已被用户终止。"
                await self.conversation_repo.append_message(ConversationMessage(
                    id="0", conversation_id=task.conversation_id, role="assistant",
                    content=cancel_msg, created_at=datetime.utcnow().isoformat()
                ))
                yield {"event": "task.output", "data": {"task_id": task_id, "stream": "stdout", "content": cancel_msg}}
                continue

            if result.exit_code != 0 or result.error:
                error_text = "命令执行失败。"
                if result.timed_out:
                    error_text = "命令执行超时，任务已被终止。"
                elif result.error:
                    error_text = f"命令执行失败: {str(result.error)}"

                await self.conversation_repo.append_message(ConversationMessage(
                    id="0", conversation_id=task.conversation_id, role="assistant",
                    content=error_text, created_at=datetime.utcnow().isoformat()
                ))
                yield {"event": "task.output", "data": {"task_id": task_id, "stream": "stderr", "content": error_text}}

                if not result.timed_out and step.repair_count < 2:
                    try:
                        repairer = TaskRepairer(llm_settings)
                        repair_result = await repairer.repair(node, task.request, step, step_outputs, error_text)

                        if repair_result.reason or repair_result.suggestion:
                            analysis = f"失败复盘：原因：{repair_result.reason}"
                            if repair_result.suggestion:
                                analysis += f"；建议：{repair_result.suggestion}"
                            await self.conversation_repo.append_message(ConversationMessage(
                                id="0", conversation_id=task.conversation_id, role="assistant",
                                content=analysis, created_at=datetime.utcnow().isoformat()
                            ))
                            yield {"event": "task.output", "data": {"task_id": task_id, "stream": "repair.analysis", "content": analysis}}

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
                            await self.conversation_repo.append_message(ConversationMessage(
                                id="0", conversation_id=task.conversation_id, role="assistant",
                                content=retry_msg, created_at=datetime.utcnow().isoformat()
                            ))
                            yield {"event": "task.output", "data": {"task_id": task_id, "stream": "repair.retry", "content": retry_msg}}

                            result = await execute_command(step.command, task_id=task_id)
                            step_outputs = []
                            for stream, content in result.lines:
                                line_text = f"[{stream}] {content}"
                                execution_outputs.append(line_text)
                                step_outputs.append(line_text)
                                await self.conversation_repo.append_message(ConversationMessage(
                                    id="0", conversation_id=task.conversation_id, role="assistant",
                                    content=line_text, created_at=datetime.utcnow().isoformat()
                                ))
                                yield {"event": "task.output", "data": {"task_id": task_id, "stream": stream, "content": content}}

                            step.repaired_output = "\n".join(step_outputs)

                            if result.exit_code == 0 and not result.error:
                                success_msg = f"第 {index+1} 步修复后执行成功。"
                                await self.conversation_repo.append_message(ConversationMessage(
                                    id="0", conversation_id=task.conversation_id, role="assistant",
                                    content=success_msg, created_at=datetime.utcnow().isoformat()
                                ))
                                step.status = TaskStepStatus.COMPLETED
                                task.steps[index] = step
                                task.progress = 55 + int(((index + 1) / len(task.steps)) * 35)
                                task.updated_at = datetime.utcnow().isoformat()
                                await self.task_repo.update_task(task_id, task)
                                continue

                    except Exception as e:
                        logger.error(f"Task repair failed: {e}")
                        error_msg = f"修复尝试失败: {str(e)}"
                        await self.conversation_repo.append_message(ConversationMessage(
                            id="0", conversation_id=task.conversation_id, role="assistant",
                            content=error_msg, created_at=datetime.utcnow().isoformat()
                        ))
                        yield {"event": "task.output", "data": {"task_id": task_id, "stream": "stderr", "content": error_msg}}

                step.status = TaskStepStatus.FAILED
                task.steps[index] = step
                task.status = TaskStatus.FAILED
                task.progress = 100
                task.summary = f"第 {index+1} 步执行失败，任务终止。"
                task.updated_at = datetime.utcnow().isoformat()
                await self.task_repo.update_task(task_id, task)

                yield {"event": "task.status", "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}}
                return

            step.status = TaskStepStatus.COMPLETED
            task.steps[index] = step
            task.progress = 55 + int(((index + 1) / len(task.steps)) * 35)
            task.updated_at = datetime.utcnow().isoformat()
            await self.task_repo.update_task(task_id, task)

        try:
            summarizer = TaskSummarizer(llm_settings)
            final_summary = await summarizer.summarize(node, task.request, task.steps, execution_outputs)
            task.final_result = final_summary
            task.summary = final_summary
        except Exception as e:
            logger.error(f"Task summarization failed: {e}")
            task.summary = "任务执行完成，但结果总结失败。"
            task.final_result = "\n".join(execution_outputs[-10:])

        now = datetime.utcnow().isoformat()
        task.status = TaskStatus.COMPLETED
        task.progress = 100
        task.updated_at = now
        await self.task_repo.update_task(task_id, task)

        yield {"event": "task.status", "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}}
        yield {"event": "task.output", "data": {"task_id": task_id, "stream": "stdout", "content": task.summary}}

    def _is_cancelled(self, task_id: str) -> bool:
        return task_id in self._cancelled_tasks

    async def _get_model_config(self, task: Task) -> Optional[ModelConfig]:
        if task.model_id:
            model = await self.model_repo.get_model(task.model_id)
            if model:
                return model
        return await self.model_repo.get_default_model()

    def _build_llm_settings(self, model_config: ModelConfig) -> LLMSettings:
        return LLMSettings(
            api_url=model_config.api_url,
            api_key=model_config.api_key,
            model=model_config.model,
            temperature=model_config.temperature,
            extra_params=model_config.extra_params or {},
            extra_body=model_config.extra_body or {},
            extra_headers=model_config.extra_headers or {},
            chat_system_prompt=self.settings.chat_system_prompt,
            task_planner_prompt=self.settings.task_planner_prompt,
            task_planner_user_prompt=self.settings.task_planner_user_prompt,
            task_windows_tool_prompt=self.settings.task_windows_tool_prompt,
            task_linux_tool_prompt=self.settings.task_linux_tool_prompt,
            task_mac_tool_prompt=self.settings.task_mac_tool_prompt,
            task_failure_repair_prompt=self.settings.task_failure_repair_prompt,
            task_command_rules_prompt=self.settings.task_command_rules_prompt,
            task_command_blacklist=self.settings.task_command_blacklist,
            task_command_whitelist=self.settings.task_command_whitelist
        )

    async def execute_task(
        self,
        task_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        task = await self.task_repo.get_task(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return

        model_config = await self._get_model_config(task)
        if not model_config:
            now = datetime.utcnow().isoformat()
            task.status = TaskStatus.FAILED
            task.progress = 100
            task.summary = "未配置模型，请先在设置页添加模型配置。"
            task.updated_at = now
            await self.task_repo.update_task(task_id, task)
            yield {"event": "task.status", "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}}
            yield {"event": "task.output", "data": {"task_id": task_id, "stream": "stderr", "content": "未配置模型，请先在设置页添加模型配置。"}}
            return

        llm_settings = self._build_llm_settings(model_config)

        node = await self.node_repo.get_node(task.node_id)
        node_label = describe_node(node) if node else f"节点 {task.node_id}"

        now = datetime.utcnow().isoformat()
        task.status = TaskStatus.ANALYZING
        task.progress = 20
        task.summary = "正在分析任务并生成执行计划。"
        task.updated_at = now
        await self.task_repo.update_task(task_id, task)

        yield {
            "event": "task.status",
            "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}
        }

        if self._is_cancelled(task_id):
            return

        history = await self.conversation_repo.get_conversation_messages(task.conversation_id)

        planning_msg = f"正在结合节点 {node_label} 分析任务并生成执行计划..."
        await self.conversation_repo.append_message(ConversationMessage(
            id="0", conversation_id=task.conversation_id, role="assistant",
            content=planning_msg, created_at=datetime.utcnow().isoformat()
        ))
        yield {"event": "task.output", "data": {"task_id": task_id, "stream": "stdout", "content": planning_msg}}

        try:
            planner = TaskPlanner(llm_settings)
            plan = await planner.generate_plan(node, task.request, history)
        except Exception as e:
            logger.error(f"Task planning failed: {e}")
            now = datetime.utcnow().isoformat()
            task.status = TaskStatus.FAILED
            task.progress = 100
            task.summary = f"节点 {node_label} 的任务规划失败：{str(e)}"
            task.updated_at = now
            await self.task_repo.update_task(task_id, task)

            yield {"event": "task.status", "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}}
            yield {"event": "task.output", "data": {"task_id": task_id, "stream": "stderr", "content": f"任务规划失败: {str(e)}"}}
            return

        if self._is_cancelled(task_id):
            return

        if plan.needs_user_input and plan.input_request:
            now = datetime.utcnow().isoformat()
            task.title = plan.title or task.title
            task.summary = plan.summary
            task.status = TaskStatus.WAITING_INPUT
            task.progress = 40
            task.input_question = plan.input_request.question
            task.input_type = plan.input_request.input_type
            task.input_options = plan.input_request.options
            task.input_placeholder = plan.input_request.placeholder
            task.updated_at = now
            await self.task_repo.update_task(task_id, task)

            yield {"event": "task.status", "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}}

            input_msg = f"需要您的输入：{plan.input_request.question}"
            if plan.input_request.options:
                input_msg += f"\n选项：{', '.join(plan.input_request.options)}"
            await self.conversation_repo.append_message(ConversationMessage(
                id="0", conversation_id=task.conversation_id, role="assistant",
                content=input_msg, created_at=datetime.utcnow().isoformat()
            ))
            yield {"event": "task.output", "data": {"task_id": task_id, "stream": "input.request", "content": input_msg}}
            yield {"event": "task.input", "data": {
                "task_id": task_id,
                "question": plan.input_request.question,
                "input_type": plan.input_request.input_type,
                "options": plan.input_request.options,
                "placeholder": plan.input_request.placeholder,
                "default_value": plan.input_request.default_value
            }}
            return

        steps = [
            TaskStep(
                index=i,
                title=step.title,
                status=TaskStepStatus.PENDING,
                command=step.command
            )
            for i, step in enumerate(plan.steps)
        ]

        pending_preview = "\n".join(f"{i+1}. {s.title}: {s.command}" for i, s in enumerate(plan.steps))

        now = datetime.utcnow().isoformat()
        task.title = plan.title or task.title
        task.pending_command = pending_preview
        task.risk_reason = plan.risk_reason
        task.summary = plan.summary
        task.steps = steps
        task.progress = 45
        task.updated_at = now

        if plan.risk_reason or plan.requires_confirmation:
            task.status = TaskStatus.WAITING_CONFIRM
            task.summary = f"{task.summary} 该计划需要人工确认后才会执行。"
            for step in task.steps:
                step.status = TaskStepStatus.WAITING_CONFIRM
        else:
            task.status = TaskStatus.EXECUTING

        await self.task_repo.update_task(task_id, task)

        yield {"event": "task.status", "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}}

        planned_msg = f"已生成 {len(task.steps)} 个执行步骤。"
        await self.conversation_repo.append_message(ConversationMessage(
            id="0", conversation_id=task.conversation_id, role="assistant",
            content=planned_msg, created_at=datetime.utcnow().isoformat()
        ))
        yield {"event": "task.output", "data": {"task_id": task_id, "stream": "plan.info", "content": planned_msg}}

        if task.status == TaskStatus.WAITING_CONFIRM:
            confirm_msg = f"该任务需要人工确认后执行。\n{pending_preview}"
            yield {"event": "task.output", "data": {"task_id": task_id, "stream": "approval", "content": confirm_msg}}
            return

        execution_outputs = []

        for index, step in enumerate(task.steps):
            if self._is_cancelled(task_id):
                return

            if not step.command.strip():
                continue

            now = datetime.utcnow().isoformat()
            task.status = TaskStatus.EXECUTING
            task.progress = 55 + int((index / len(task.steps)) * 35)
            task.summary = f"正在执行第 {index+1}/{len(task.steps)} 步：{step.title}"
            task.updated_at = now
            step.status = TaskStepStatus.EXECUTING
            task.steps[index] = step
            await self.task_repo.update_task(task_id, task)

            yield {"event": "task.status", "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}}

            start_msg = f"开始执行第 {index+1} 步：{step.title}\n命令：{step.command}"
            await self.conversation_repo.append_message(ConversationMessage(
                id="0", conversation_id=task.conversation_id, role="assistant",
                content=start_msg, created_at=datetime.utcnow().isoformat()
            ))
            yield {"event": "task.output", "data": {"task_id": task_id, "stream": "step.start", "content": start_msg}}

            result = await execute_command(step.command, task_id=task_id)
            step_outputs = []
            for stream, content in result.lines:
                line_text = f"[{stream}] {content}"
                execution_outputs.append(line_text)
                step_outputs.append(line_text)
                await self.conversation_repo.append_message(ConversationMessage(
                    id="0", conversation_id=task.conversation_id, role="assistant",
                    content=line_text, created_at=datetime.utcnow().isoformat()
                ))
                yield {"event": "task.output", "data": {"task_id": task_id, "stream": stream, "content": content}}

            step.result_output = "\n".join(step_outputs)

            if self._is_cancelled(task_id):
                return

            if result.cancelled:
                step.status = TaskStepStatus.CANCELLED
                cancel_msg = "进程已被用户终止。"
                await self.conversation_repo.append_message(ConversationMessage(
                    id="0", conversation_id=task.conversation_id, role="assistant",
                    content=cancel_msg, created_at=datetime.utcnow().isoformat()
                ))
                yield {"event": "task.output", "data": {"task_id": task_id, "stream": "stdout", "content": cancel_msg}}
                continue

            if result.exit_code != 0 or result.error:
                error_text = "命令执行失败。"
                if result.timed_out:
                    error_text = "命令执行超时，任务已被终止。"
                elif result.error:
                    error_text = f"命令执行失败: {str(result.error)}"

                await self.conversation_repo.append_message(ConversationMessage(
                    id="0", conversation_id=task.conversation_id, role="assistant",
                    content=error_text, created_at=datetime.utcnow().isoformat()
                ))
                yield {"event": "task.output", "data": {"task_id": task_id, "stream": "stderr", "content": error_text}}

                if not result.timed_out and step.repair_count < 2:
                    try:
                        repairer = TaskRepairer(llm_settings)
                        repair_result = await repairer.repair(node, task.request, step, step_outputs, error_text)

                        if repair_result.reason or repair_result.suggestion:
                            analysis = f"失败复盘：原因：{repair_result.reason}"
                            if repair_result.suggestion:
                                analysis += f"；建议：{repair_result.suggestion}"
                            await self.conversation_repo.append_message(ConversationMessage(
                                id="0", conversation_id=task.conversation_id, role="assistant",
                                content=analysis, created_at=datetime.utcnow().isoformat()
                            ))
                            yield {"event": "task.output", "data": {"task_id": task_id, "stream": "repair.analysis", "content": analysis}}

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
                            await self.conversation_repo.append_message(ConversationMessage(
                                id="0", conversation_id=task.conversation_id, role="assistant",
                                content=retry_msg, created_at=datetime.utcnow().isoformat()
                            ))
                            yield {"event": "task.output", "data": {"task_id": task_id, "stream": "repair.retry", "content": retry_msg}}

                            result = await execute_command(step.command, task_id=task_id)
                            step_outputs = []
                            for stream, content in result.lines:
                                line_text = f"[{stream}] {content}"
                                execution_outputs.append(line_text)
                                step_outputs.append(line_text)
                                await self.conversation_repo.append_message(ConversationMessage(
                                    id="0", conversation_id=task.conversation_id, role="assistant",
                                    content=line_text, created_at=datetime.utcnow().isoformat()
                                ))
                                yield {"event": "task.output", "data": {"task_id": task_id, "stream": stream, "content": content}}

                            step.repaired_output = "\n".join(step_outputs)

                            if result.exit_code == 0 and not result.error:
                                success_msg = f"第 {index+1} 步修复后执行成功。"
                                await self.conversation_repo.append_message(ConversationMessage(
                                    id="0", conversation_id=task.conversation_id, role="assistant",
                                    content=success_msg, created_at=datetime.utcnow().isoformat()
                                ))
                                step.status = TaskStepStatus.COMPLETED
                                task.steps[index] = step
                                task.progress = 55 + int(((index + 1) / len(task.steps)) * 35)
                                task.updated_at = datetime.utcnow().isoformat()
                                await self.task_repo.update_task(task_id, task)
                                continue

                    except Exception as e:
                        logger.error(f"Task repair failed: {e}")
                        error_msg = f"修复尝试失败: {str(e)}"
                        await self.conversation_repo.append_message(ConversationMessage(
                            id="0", conversation_id=task.conversation_id, role="assistant",
                            content=error_msg, created_at=datetime.utcnow().isoformat()
                        ))
                        yield {"event": "task.output", "data": {"task_id": task_id, "stream": "stderr", "content": error_msg}}

                step.status = TaskStepStatus.FAILED
                task.steps[index] = step
                task.status = TaskStatus.FAILED
                task.progress = 100
                task.summary = f"第 {index+1} 步执行失败，任务终止。"
                task.updated_at = datetime.utcnow().isoformat()
                await self.task_repo.update_task(task_id, task)

                yield {"event": "task.status", "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}}
                return

            step.status = TaskStepStatus.COMPLETED
            task.steps[index] = step
            task.progress = 55 + int(((index + 1) / len(task.steps)) * 35)
            task.updated_at = datetime.utcnow().isoformat()
            await self.task_repo.update_task(task_id, task)

        try:
            summarizer = TaskSummarizer(llm_settings)
            final_summary = await summarizer.summarize(node, task.request, task.steps, execution_outputs)
            task.final_result = final_summary
            task.summary = final_summary
        except Exception as e:
            logger.error(f"Task summarization failed: {e}")
            task.summary = "任务执行完成，但结果总结失败。"
            task.final_result = "\n".join(execution_outputs[-10:])

        now = datetime.utcnow().isoformat()
        task.status = TaskStatus.COMPLETED
        task.progress = 100
        task.updated_at = now
        await self.task_repo.update_task(task_id, task)

        yield {"event": "task.status", "data": {"task_id": task_id, "status": task.status.value, "progress": task.progress}}
        yield {"event": "task.output", "data": {"task_id": task_id, "stream": "stdout", "content": task.summary}}
