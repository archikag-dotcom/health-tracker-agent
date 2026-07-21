"""
ADK Tool Decorator and Runtime Wrapper.
Enforces strict input/output Pydantic validation, explicit parameter descriptions, and structured recovery guidance on errors.
"""
import inspect
from typing import Callable, Any, Dict, Type, get_type_hints, Optional
from pydantic import BaseModel, ValidationError
from .schemas import ToolMetadata, ToolParameterDoc, ToolResult, ToolErrorDetail


class ADKTool:
    """Wrapper around a Python tool function enforcing schemas and safe error handling."""

    def __init__(
        self,
        func: Callable[..., Any],
        name: Optional[str] = None,
        description: Optional[str] = None,
        input_schema: Optional[Type[BaseModel]] = None,
        output_schema: Optional[Type[BaseModel]] = None,
    ):
        self.func = func
        self.name = name or func.__name__
        self.description = description or (func.__doc__.strip() if func.__doc__ else "No description provided.")
        self.input_schema_cls = input_schema
        self.output_schema_cls = output_schema

        # Introspect function parameters for human-readable documentation
        self.parameter_docs = self._build_parameter_docs()

    def __call__(self, *args, **kwargs):
        """Allows direct Python function call on the ADKTool instance."""
        return self.func(*args, **kwargs)

    def _build_parameter_docs(self) -> list[ToolParameterDoc]:
        docs = []
        sig = inspect.signature(self.func)
        type_hints = get_type_hints(self.func)

        # Parse docstring param descriptions if available
        param_descriptions = {}
        if self.func.__doc__:
            for line in self.func.__doc__.splitlines():
                line = line.strip()
                if line.startswith(":param") or line.startswith("Args:"):
                    parts = line.split(":", 2)
                    if len(parts) >= 3 and parts[0].strip() == ":param":
                        p_name = parts[1].strip()
                        p_desc = parts[2].strip()
                        param_descriptions[p_name] = p_desc

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            param_type = type_hints.get(param_name, Any)
            type_str = getattr(param_type, "__name__", str(param_type))
            desc = param_descriptions.get(param_name, f"Parameter {param_name} of type {type_str}")
            is_req = param.default == inspect.Parameter.empty
            default_val = None if is_req else param.default

            docs.append(
                ToolParameterDoc(
                    name=param_name,
                    type_name=type_str,
                    description=desc,
                    required=is_req,
                    default_value=default_val,
                )
            )
        return docs

    def get_metadata(self) -> ToolMetadata:
        input_schema_dict = self.input_schema_cls.model_json_schema() if self.input_schema_cls else {}
        output_schema_dict = self.output_schema_cls.model_json_schema() if self.output_schema_cls else {}

        return ToolMetadata(
            name=self.name,
            description=self.description,
            parameters=self.parameter_docs,
            input_schema=input_schema_dict,
            output_schema=output_schema_dict,
        )

    def execute(self, **kwargs) -> ToolResult:
        """Executes tool with input/output validation, OpenTelemetry spans, and PRE/POST structured logs."""
        from adk.logging import StructuredLogger
        from adk.tracing import Tracer
        import time

        logger = StructuredLogger(agent_name=f"Tool:{self.name}")
        start_time = time.time()
        trace_id = Tracer.get_current_trace_id()

        with Tracer.span(name=f"Tool:{self.name}", attributes=kwargs) as span:
            span_id = span.span_id

            logger.log_action_intent(
                intended_action=f"ExecuteTool:{self.name}",
                trace_id=trace_id,
                span_id=span_id,
                parameters=kwargs,
            )

            # 1. Input Schema Validation
            validated_input = kwargs
            if self.input_schema_cls:
                try:
                    validated_model = self.input_schema_cls(**kwargs)
                    validated_input = validated_model.model_dump()
                except ValidationError as e:
                    invalid_fields = {".".join(str(loc) for loc in err["loc"]): err["msg"] for err in e.errors()}
                    recovery_msg = f"Input validation failed for tool '{self.name}'. Please correct: {invalid_fields}."
                    logger.log_action_outcome(intended_action=f"ExecuteTool:{self.name}", trace_id=trace_id, span_id=span_id, duration_ms=(time.time()-start_time)*1000, success=False, error=recovery_msg)
                    return ToolResult(success=False, tool_name=self.name, error=ToolErrorDetail(error_code="INVALID_INPUT_SCHEMA", message=f"Validation failed", invalid_parameters=invalid_fields, recovery_instructions=recovery_msg))

            # 2. Function Execution
            try:
                raw_result = self.func(**validated_input)

                # 3. Output Schema Validation
                if self.output_schema_cls:
                    if isinstance(raw_result, dict): validated_output = self.output_schema_cls(**raw_result).model_dump()
                    elif isinstance(raw_result, self.output_schema_cls): validated_output = raw_result.model_dump()
                    else: validated_output = raw_result
                else: validated_output = raw_result

                logger.log_action_outcome(intended_action=f"ExecuteTool:{self.name}", trace_id=trace_id, span_id=span_id, duration_ms=(time.time()-start_time)*1000, success=True, outcome_data=validated_output)
                return ToolResult(success=True, data=validated_output, tool_name=self.name)

            except Exception as ex:
                logger.log_action_outcome(intended_action=f"ExecuteTool:{self.name}", trace_id=trace_id, span_id=span_id, duration_ms=(time.time()-start_time)*1000, success=False, error=str(ex))
                return ToolResult(success=False, tool_name=self.name, error=ToolErrorDetail(error_code="EXECUTION_ERROR", message=str(ex), recovery_instructions=str(ex)))


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    input_schema: Optional[Type[BaseModel]] = None,
    output_schema: Optional[Type[BaseModel]] = None,
):
    """Decorator to convert a Python function into an ADK Tool with strict Pydantic schemas."""
    def decorator(func: Callable[..., Any]) -> ADKTool:
        return ADKTool(
            func=func,
            name=name,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
        )
    return decorator
