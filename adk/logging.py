"""
Structured Logging & PII Redaction Module.
Captures rich structured metadata and scrubs sensitive data prior to storage or output.
"""
import os
import logging
import json
import re
from typing import Dict, Any, Optional
from datetime import datetime


class Redactor:
    """Active PII scrubbing engine redacting sensitive fields before logging or storage."""

    PII_PATTERNS = [
        (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[REDACTED_EMAIL]'),
        (r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', '[REDACTED_PHONE]'),
        (r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED_SSN]'),
        (r'\b(?:\d[ -]*?){13,16}\b', '[REDACTED_CARD_NUMBER]'),
        (r'(?i)(api[_-]?key|secret|password|bearer)\s*[:=]\s*["\']?[a-zA-Z0-9_\-\.]{8,}["\']?', r'\1: [REDACTED_CREDENTIAL]'),
    ]

    @classmethod
    def scrub_text(cls, text: str) -> str:
        if not text or not isinstance(text, str):
            return str(text) if text is not None else ""
        scrubbed = text
        for pattern, replacement in cls.PII_PATTERNS:
            scrubbed = re.sub(pattern, replacement, scrubbed)
        return scrubbed

    @classmethod
    def scrub_dict(cls, obj: Any) -> Any:
        """Recursively scrubs PII from dictionaries, lists, and strings."""
        if isinstance(obj, str):
            return cls.scrub_text(obj)
        elif isinstance(obj, dict):
            return {k: cls.scrub_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [cls.scrub_dict(item) for item in obj]
        return obj


class StructuredLogger:
    """Structured JSON Logger recording pre-execution intention and post-execution outcome."""

    def __init__(self, agent_name: str = "ADKAgent"):
        self.agent_name = agent_name
        self.logger = logging.getLogger(f"adk.{agent_name}")
        self.disabled = os.environ.get("DISABLE_LOGGING", "").lower() in ("true", "1", "yes")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(handler)
            log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
            self.logger.setLevel(log_level)

    def log_action_intent(
        self,
        intended_action: str,
        trace_id: str,
        span_id: str,
        parameters: Dict[str, Any],
    ):
        """Records PRE_EXECUTION intent before action execution."""
        if self.disabled:
            return
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "phase": "PRE_EXECUTION",
            "agent_name": self.agent_name,
            "intended_action": intended_action,
            "trace_id": trace_id,
            "span_id": span_id,
            "parameters": Redactor.scrub_dict(parameters),
        }
        self.logger.info(json.dumps(payload))

    def log_action_outcome(
        self,
        intended_action: str,
        trace_id: str,
        span_id: str,
        duration_ms: float,
        success: bool,
        outcome_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        """Records POST_EXECUTION outcome after action execution."""
        if self.disabled:
            return
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO" if success else "ERROR",
            "phase": "POST_EXECUTION",
            "agent_name": self.agent_name,
            "intended_action": intended_action,
            "trace_id": trace_id,
            "span_id": span_id,
            "duration_ms": round(duration_ms, 2),
            "success": success,
            "outcome_data": Redactor.scrub_dict(outcome_data) if outcome_data else None,
            "error": Redactor.scrub_text(error) if error else None,
        }
        self.logger.info(json.dumps(payload))
