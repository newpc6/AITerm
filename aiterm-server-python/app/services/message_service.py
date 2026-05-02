import json
from typing import Dict, Any, List, Optional
from app.models.chat import MessageType
from app.repositories.message import MessageRepository


class MessageService:
    def __init__(self):
        self.message_repo = MessageRepository()

    async def save_text_message(self, chat_id: str, role: str, content: str) -> Dict[str, Any]:
        message = await self.message_repo.create_message(
            chat_id=chat_id,
            role=role,
            content=content,
            type=MessageType.TEXT.value,
            metadata={}
        )
        return message.model_dump()

    async def save_plan_message(self, chat_id: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        content_lines = ["步骤规划"]
        for step in steps:
            content_lines.append(f"{step['index'] + 1}. {step['title']}")
        
        content = "\n".join(content_lines)
        metadata = {"steps": steps}
        
        message = await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=content,
            type=MessageType.PLAN.value,
            metadata=metadata
        )
        return message.model_dump()

    async def save_step_message(
        self, 
        chat_id: str, 
        index: int, 
        title: str, 
        command: str,
        status: str = "pending"
    ) -> Dict[str, Any]:
        content = f"第 {index + 1} 步\n{title}\n{command}"
        metadata = {
            "index": index,
            "title": title,
            "command": command,
            "status": status
        }
        
        message = await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=content,
            type=MessageType.STEP.value,
            metadata=metadata
        )
        return message.model_dump()

    async def save_step_result_message(
        self,
        chat_id: str,
        index: int,
        title: str,
        command: str,
        output: Optional[str] = None,
        exit_code: int = 0,
        success: bool = True
    ) -> Dict[str, Any]:
        if success:
            content = f"第 {index + 1} 步执行成功"
            if output:
                content += f"\n{output}"
        else:
            content = f"第 {index + 1} 步执行失败"
            if output:
                content += f"\n{output}"
        
        metadata = {
            "index": index,
            "title": title,
            "command": command,
            "output": output,
            "exit_code": exit_code,
            "success": success
        }
        
        message = await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=content,
            type=MessageType.STEP_RESULT.value,
            metadata=metadata
        )
        return message.model_dump()

    async def save_approval_message(
        self, 
        chat_id: str, 
        commands: List[str], 
        reason: str
    ) -> Dict[str, Any]:
        content = f"需要确认\n原因：{reason}\n命令：\n" + "\n".join(commands)
        metadata = {
            "commands": commands,
            "reason": reason
        }
        
        message = await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=content,
            type=MessageType.APPROVAL.value,
            metadata=metadata
        )
        return message.model_dump()

    async def save_approved_message(self, chat_id: str, commands: List[str]) -> Dict[str, Any]:
        content = "已批准\n✓\n命令：\n" + "\n".join(commands)
        metadata = {"commands": commands}
        
        message = await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=content,
            type=MessageType.APPROVED.value,
            metadata=metadata
        )
        return message.model_dump()

    async def save_rejected_message(
        self, 
        chat_id: str, 
        commands: List[str], 
        reason: str
    ) -> Dict[str, Any]:
        content = f"已拒绝\n原因：{reason}"
        metadata = {
            "commands": commands,
            "reason": reason
        }
        
        message = await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=content,
            type=MessageType.REJECTED.value,
            metadata=metadata
        )
        return message.model_dump()

    async def save_input_message(
        self,
        chat_id: str,
        question: str,
        input_type: str = "text",
        options: List[str] = None,
        placeholder: str = ""
    ) -> Dict[str, Any]:
        content = f"需要您的输入：{question}"
        if options:
            content += f"\n选项：{', '.join(options)}"
        
        metadata = {
            "question": question,
            "input_type": input_type,
            "options": options or [],
            "placeholder": placeholder
        }
        
        message = await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=content,
            type=MessageType.INPUT.value,
            metadata=metadata
        )
        return message.model_dump()

    async def save_input_response_message(
        self, 
        chat_id: str, 
        question: str, 
        answer: str
    ) -> Dict[str, Any]:
        content = f"已输入\n您的回答：{answer}"
        metadata = {
            "question": question,
            "answer": answer
        }
        
        message = await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=content,
            type=MessageType.INPUT_RESPONSE.value,
            metadata=metadata
        )
        return message.model_dump()

    async def save_output_message(
        self,
        chat_id: str,
        command: str,
        output: Optional[str] = None,
        exit_code: int = 0
    ) -> Dict[str, Any]:
        content = output or "命令执行成功，无输出。"
        metadata = {
            "command": command,
            "output": output,
            "exit_code": exit_code
        }
        
        message = await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=content,
            type=MessageType.OUTPUT.value,
            metadata=metadata
        )
        return message.model_dump()

    async def save_error_message(
        self, 
        chat_id: str, 
        message: str, 
        details: Optional[str] = None
    ) -> Dict[str, Any]:
        content = f"[错误] {message}"
        if details:
            content += f"\n{details}"
        
        metadata = {
            "message": message,
            "details": details
        }
        
        msg = await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=content,
            type=MessageType.ERROR.value,
            metadata=metadata
        )
        return msg.model_dump()

    async def save_summary_message(self, chat_id: str, summary: str) -> Dict[str, Any]:
        message = await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=summary,
            type=MessageType.SUMMARY.value,
            metadata={}
        )
        return message.model_dump()

    async def save_analysis_message(
        self, 
        chat_id: str, 
        reason: str, 
        suggestion: Optional[str] = None
    ) -> Dict[str, Any]:
        content = f"[分析] {reason}"
        if suggestion:
            content += f"\n建议：{suggestion}"
        
        metadata = {
            "reason": reason,
            "suggestion": suggestion
        }
        
        message = await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=content,
            type=MessageType.ANALYSIS.value,
            metadata=metadata
        )
        return message.model_dump()

    async def save_retry_message(
        self,
        chat_id: str,
        index: int,
        title: str,
        old_command: str,
        new_command: str,
        reason: str
    ) -> Dict[str, Any]:
        content = f"[重试] 第 {index + 1} 步\n{title}\n原命令：{old_command}\n新命令：{new_command}\n原因：{reason}"
        metadata = {
            "index": index,
            "title": title,
            "old_command": old_command,
            "new_command": new_command,
            "reason": reason
        }
        
        message = await self.message_repo.create_message(
            chat_id=chat_id,
            role="assistant",
            content=content,
            type=MessageType.RETRY.value,
            metadata=metadata
        )
        return message.model_dump()
