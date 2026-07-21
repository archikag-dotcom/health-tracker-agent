"""
OpenTelemetry Distributed Tracing & Span Context Module.
Links parent and child spans to trace execution from user query to tool completion.
"""
import uuid
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class Span(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)

    def finish(self):
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000.0, 2)


class Tracer:
    """OpenTelemetry-compatible distributed tracer managing trace contexts and nested spans."""

    _active_trace_id: Optional[str] = None
    _span_stack: List[Span] = []
    _completed_spans: List[Span] = []

    @classmethod
    def start_trace(cls, trace_id: Optional[str] = None) -> str:
        """Starts a new trace root or reuses existing trace ID."""
        cls._active_trace_id = trace_id or f"trace_{uuid.uuid4().hex[:12]}"
        cls._span_stack = []
        cls._completed_spans = []
        return cls._active_trace_id

    @classmethod
    def get_current_trace_id(cls) -> str:
        if not cls._active_trace_id:
            cls.start_trace()
        return cls._active_trace_id

    @classmethod
    def get_current_span_id(cls) -> Optional[str]:
        if cls._span_stack:
            return cls._span_stack[-1].span_id
        return None

    @classmethod
    def span(cls, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Context manager for creating nested OpenTelemetry trace spans."""
        return _SpanContextManager(name, attributes or {})

    @classmethod
    def record_span(cls, span: Span):
        cls._completed_spans.append(span)

    @classmethod
    def get_trace_summary(cls) -> Dict[str, Any]:
        """Returns recorded spans for current trace."""
        return {
            "trace_id": cls.get_current_trace_id(),
            "total_spans": len(cls._completed_spans),
            "spans": [s.model_dump() for s in cls._completed_spans],
        }


class _SpanContextManager:
    """Context manager executing span lifecycle."""

    def __init__(self, name: str, attributes: Dict[str, Any]):
        self.name = name
        self.attributes = attributes
        self.span: Optional[Span] = None

    def __enter__(self) -> Span:
        trace_id = Tracer.get_current_trace_id()
        parent_span_id = Tracer.get_current_span_id()
        span_id = f"span_{uuid.uuid4().hex[:8]}"

        self.span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=self.name,
            start_time=time.time(),
            attributes=self.attributes,
        )
        Tracer._span_stack.append(self.span)
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            self.span.finish()
            if Tracer._span_stack and Tracer._span_stack[-1].span_id == self.span.span_id:
                Tracer._span_stack.pop()
            Tracer.record_span(self.span)
