"""
ADK Schemas - Core Pydantic models for tools, parameters, state, and structured error responses.
"""
from typing import Any, Dict, List, Optional, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ToolParameterDoc(BaseModel):
    """Description of a tool parameter for LLMs and human callers."""
    name: str = Field(..., description="The parameter name.")
    type_name: str = Field(..., description="Data type of the parameter (e.g. str, int, float, List[str]).")
    description: str = Field(..., description="Clear human-readable description of what this parameter represents.")
    required: bool = Field(True, description="Whether this parameter is required.")
    default_value: Optional[Any] = Field(None, description="Default value if parameter is optional.")


class ToolMetadata(BaseModel):
    """Metadata describing a tool function, its purpose, and all input parameters."""
    name: str = Field(..., description="Highly specific and clear tool name (e.g. parse_text_meal_macros).")
    description: str = Field(..., description="Clear human-readable description of the tool's purpose and functionality.")
    parameters: List[ToolParameterDoc] = Field(default_factory=list, description="List of parameter documentation entries.")
    input_schema: Dict[str, Any] = Field(..., description="JSON Schema dict for input validation.")
    output_schema: Dict[str, Any] = Field(..., description="JSON Schema dict for output validation.")


class ToolErrorDetail(BaseModel):
    """Structured error payload providing descriptive recovery instructions for the LLM."""
    error_code: str = Field(..., description="Specific machine-readable error identifier.")
    message: str = Field(..., description="Human-readable explanation of why the tool execution failed.")
    invalid_parameters: Dict[str, str] = Field(default_factory=dict, description="Dictionary mapping parameter names to validation error reasons.")
    recovery_instructions: str = Field(..., description="Clear instructions guiding the caller on how to fix arguments or recover.")


class ToolResult(BaseModel, Generic[T]):
    """Strict output schema returned by every ADK tool call."""
    success: bool = Field(..., description="True if tool executed cleanly without errors; False otherwise.")
    data: Optional[T] = Field(None, description="Typed output payload if tool execution succeeded.")
    error: Optional[ToolErrorDetail] = Field(None, description="Detailed error information with recovery guidance if tool execution failed.")
    tool_name: str = Field(..., description="Name of the tool that generated this result.")


class AgentState(BaseModel):
    """Shared state object across Root Agent and Subagents."""
    session_id: str = Field(default="default_session", description="Unique identifier for current tracking session.")
    user_id: str = Field(default="default_user", description="Identifier for the user.")
    logs: List[Dict[str, Any]] = Field(default_factory=list, description="Audit log of actions taken.")
    context_data: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary context data passed between agents.")
