"""
ADK Base Agent Architecture.
Provides base classes for specialized SubAgents and Root Orchestrator Agent.
"""
from typing import Dict, List, Any, Optional
from .schemas import AgentState, ToolResult
from .tools import ADKTool
from adk.constitution import DEFAULT_CONSTITUTION, AgentConstitution
from adk.context import ContextManager


class BaseAgent:
    """Base ADK Agent class managing tools and execution state."""

    def __init__(
        self,
        name: str,
        description: str,
        role: str,
        constitution: Optional[AgentConstitution] = None,
        max_context_tokens: int = 2500,
    ):
        self.name = name
        self.description = description
        self.role = role
        self.constitution = constitution or DEFAULT_CONSTITUTION
        self.context_manager = ContextManager(max_token_budget=max_context_tokens)
        self.tools: Dict[str, ADKTool] = {}
        self.state = AgentState()

    def register_tool(self, tool_obj: ADKTool) -> None:
        """Registers an ADK tool with strict Pydantic validation."""
        self.tools[tool_obj.name] = tool_obj

    def get_tool(self, name: str) -> Optional[ADKTool]:
        return self.tools.get(name)

    def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """Executes a registered tool by name with error handling."""
        tool_obj = self.get_tool(tool_name)
        if not tool_obj:
            available_tools = list(self.tools.keys())
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error={
                    "error_code": "TOOL_NOT_FOUND",
                    "message": f"Tool '{tool_name}' is not registered on agent '{self.name}'.",
                    "recovery_instructions": f"Available tools on agent '{self.name}' are: {available_tools}. Select one of these tools.",
                },
            )
        result = tool_obj.execute(**kwargs)
        # Log to agent state
        self.state.logs.append({
            "agent": self.name,
            "tool": tool_name,
            "success": result.success,
            "data": result.data,
            "error": result.error.model_dump() if result.error else None,
        })
        return result


class SubAgent(BaseAgent):
    """Specialized SubAgent handling a focused sub-domain task."""
    pass


class RootAgent(BaseAgent):
    """Root Orchestrator Agent managing specialized subagents."""

    def __init__(self, name: str, description: str):
        super().__init__(name=name, description=description, role="Orchestrator")
        self.subagents: Dict[str, SubAgent] = {}

    def register_subagent(self, subagent: SubAgent) -> None:
        """Registers a specialized subagent under the root orchestrator."""
        self.subagents[subagent.name] = subagent

    def get_subagent(self, name: str) -> Optional[SubAgent]:
        return self.subagents.get(name)
