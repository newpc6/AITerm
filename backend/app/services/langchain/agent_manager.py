import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.models.model_setting import ModelConfig
from app.services.langchain.chat_model import AITermChatModel, create_chat_model
from app.services.langchain.tool_adapter import AITermToolAdapter

logger = logging.getLogger("aiterm")


class LangChainAgentManager:
    def __init__(
        self,
        model_config: ModelConfig,
        tools: List[Dict[str, Any]],
        system_prompt: str = "",
        max_iterations: int = 10,
        tool_service: Any = None,
        chat_id: str = None,
    ):
        self.model_config = model_config
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.tool_service = tool_service
        self.chat_id = chat_id

        self.chat_model = create_chat_model(model_config)

        self.langchain_tools = [
            AITermToolAdapter(
                tool_data=t, tool_service=tool_service, chat_id=chat_id)
            for t in tools
        ]

        self.prompt = self._build_prompt()
        self.agent = create_openai_tools_agent(
            self.chat_model, self.langchain_tools, self.prompt)
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.langchain_tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=max_iterations,
            return_intermediate_steps=True,
        )

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", self.system_prompt or "你是一个有用的AI助手。请使用工具帮助用户完成任务。"),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

    def _convert_history(self, history: List[Dict[str, Any]]) -> List:
        messages = []
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        return messages

    async def run(self, user_input: str, history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        history_messages = self._convert_history(history or [])

        result = await self.executor.ainvoke({
            "input": user_input,
            "chat_history": history_messages,
        })

        return {
            "output": result.get("output", ""),
            "intermediate_steps": result.get("intermediate_steps", []),
        }

    async def stream(
        self, user_input: str, history: List[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        history_messages = self._convert_history(history or [])

        current_iteration = 0
        reasoning_started = False

        try:
            async for event in self.executor.astream_events(
                {"input": user_input, "chat_history": history_messages},
                version="v2",
            ):
                kind = event.get("event", "")

                if kind == "on_chat_model_stream":
                    data = event.get("data", {})
                    chunk = data.get("chunk")
                    if chunk and chunk.content:
                        yield {
                            "type": "content",
                            "delta": chunk.content,
                            "iteration": current_iteration + 1,
                        }

                elif kind == "on_tool_start":
                    data = event.get("data", {})
                    tool_name = event.get("name", "")
                    tool_input = data.get("input", {})
                    current_iteration += 1
                    yield {
                        "type": "tool_start",
                        "tool": tool_name,
                        "input": tool_input,
                        "iteration": current_iteration,
                    }

                elif kind == "on_tool_end":
                    tool_output = event.get("data", {}).get("output", "")
                    yield {
                        "type": "tool_end",
                        "output": tool_output,
                        "iteration": current_iteration,
                    }

                elif kind == "on_chain_end":
                    pass

        except Exception as e:
            logger.error(f"Agent stream error: {e}")
            yield {
                "type": "error",
                "error": str(e),
            }
