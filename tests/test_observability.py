"""
Unit tests for Observability, OpenTelemetry Distributed Tracing, Structured Logging, and PII Redaction.
"""
import unittest
import json
import io
import logging
from adk.logging import StructuredLogger, Redactor
from adk.tracing import Tracer
from services.vector_memory import PersistentVectorMemoryBank


class TestObservabilityAndTracing(unittest.TestCase):

    def test_pii_redactor(self):
        """Verify Redactor scrubs emails, phone numbers, SSNs, credit cards, and credentials."""
        raw_text = "User email is john.doe@example.com and phone is (555) 123-4567. Card: 4111111111111111, api_key: 'secret_12345678'."
        scrubbed = Redactor.scrub_text(raw_text)
        
        self.assertNotIn("john.doe@example.com", scrubbed)
        self.assertIn("[REDACTED_EMAIL]", scrubbed)
        self.assertNotIn("(555) 123-4567", scrubbed)
        self.assertIn("[REDACTED_PHONE]", scrubbed)
        self.assertIn("[REDACTED_CARD_NUMBER]", scrubbed)
        self.assertIn("[REDACTED_CREDENTIAL]", scrubbed)

        dict_payload = {
            "user": "Alice",
            "email": "alice@gmail.com",
            "notes": ["Call me at 555-987-6543"],
        }
        scrubbed_dict = Redactor.scrub_dict(dict_payload)
        self.assertEqual(scrubbed_dict["email"], "[REDACTED_EMAIL]")
        self.assertIn("[REDACTED_PHONE]", scrubbed_dict["notes"][0])

    def test_opentelemetry_tracer_spans(self):
        """Verify OpenTelemetry Tracer manages trace context and linked nested spans."""
        trace_id = Tracer.start_trace()
        self.assertIsNotNone(trace_id)

        with Tracer.span("ParentSpan", attributes={"service": "root_agent"}) as parent:
            self.assertEqual(Tracer.get_current_span_id(), parent.span_id)
            
            with Tracer.span("ChildSpan", attributes={"tool": "parse_meal"}) as child:
                self.assertEqual(child.parent_span_id, parent.span_id)
                self.assertEqual(child.trace_id, trace_id)

        summary = Tracer.get_trace_summary()
        self.assertEqual(summary["total_spans"], 2)
        spans = summary["spans"]
        self.assertEqual(spans[0]["name"], "ChildSpan")
        self.assertEqual(spans[1]["name"], "ParentSpan")
        self.assertIsNotNone(spans[0]["duration_ms"])

    def test_structured_logger_lifecycle(self):
        """Verify StructuredLogger emits JSON logs with PRE_EXECUTION intent and POST_EXECUTION outcome."""
        logger = StructuredLogger(agent_name="TestAgent")
        
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.logger.addHandler(handler)

        trace_id = "trace_test123"
        span_id = "span_test456"

        logger.log_action_intent(
            intended_action="ExecuteTool:parse_text_meal_macros",
            trace_id=trace_id,
            span_id=span_id,
            parameters={"text": "3 eggs", "email": "user@test.com"},
        )

        logger.log_action_outcome(
            intended_action="ExecuteTool:parse_text_meal_macros",
            trace_id=trace_id,
            span_id=span_id,
            duration_ms=12.5,
            success=True,
            outcome_data={"calories": 216.0},
        )

        output_lines = log_stream.getvalue().strip().split("\n")
        self.assertEqual(len(output_lines), 2)

        pre_log = json.loads(output_lines[0])
        self.assertEqual(pre_log["phase"], "PRE_EXECUTION")
        self.assertEqual(pre_log["intended_action"], "ExecuteTool:parse_text_meal_macros")
        self.assertEqual(pre_log["parameters"]["email"], "[REDACTED_EMAIL]")

        post_log = json.loads(output_lines[1])
        self.assertEqual(post_log["phase"], "POST_EXECUTION")
        self.assertEqual(post_log["duration_ms"], 12.5)
        self.assertTrue(post_log["success"])

    def test_vector_memory_pii_scrubbing(self):
        """Verify vector memory bank scrubs sensitive data before indexing."""
        bank = PersistentVectorMemoryBank(storage_path="data/test_obs_vector.json")
        bank.add_document("doc_pii", "User email alice.smith@work.org logged 2 eggs", metadata={"user_email": "alice.smith@work.org"})
        
        indexed_doc = bank.documents["doc_pii"]
        self.assertNotIn("alice.smith@work.org", indexed_doc.content)
        self.assertIn("[REDACTED_EMAIL]", indexed_doc.content)


if __name__ == "__main__":
    unittest.main()
