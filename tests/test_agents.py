"""
Unit tests for Python ADK Health Tracker Agent, Tools, SubAgents, and Error Handling.
"""
import unittest
import os
from adk.tools import ADKTool
from models.schemas import UserProfile, MealType, FitnessGoal
from agents.meal_analysis_agent import MealAnalysisSubAgent, parse_text_meal_macros
from agents.daily_report_agent import DailyReportSubAgent, calculate_daily_macro_totals
from agents.root_agent import HealthTrackerRootAgent
from services.storage import DATA_FILE


class TestADKAgents(unittest.TestCase):

    def setUp(self):
        """Clean persistent storage before running tests."""
        if os.path.exists(DATA_FILE):
            try:
                os.remove(DATA_FILE)
            except Exception:
                pass

    def test_tool_metadata_and_parameter_docs(self):
        """Verify tool functions include clear, human-readable descriptions and strict schemas."""
        metadata = parse_text_meal_macros.get_metadata()
        self.assertEqual(metadata.name, "parse_text_meal_macros")
        self.assertIn("Parses natural language text meal descriptions", metadata.description)
        self.assertGreaterEqual(len(metadata.parameters), 1)
        raw_text_doc = next(p for p in metadata.parameters if p.name == "raw_text")
        self.assertTrue(raw_text_doc.required)
        self.assertIn("raw_text", metadata.input_schema["properties"])

    def test_meal_analysis_subagent_text_logging(self):
        """Verify parse_text_meal_macros tool calculates protein and macros accurately."""
        subagent = MealAnalysisSubAgent()
        result = subagent.execute_tool(
            "parse_text_meal_macros",
            raw_text="3 eggs, 2 slices toast, 1/2 avocado",
            meal_type="breakfast",
        )
        self.assertTrue(result.success)
        self.assertIsNotNone(result.data)
        meal_log = result.data["meal_log"]
        self.assertEqual(meal_log["meal_type"], "breakfast")
        macros = meal_log["total_macros"]
        # 3 eggs + 2 toast + 1/2 avocado >= 20g protein
        self.assertGreaterEqual(macros["protein_g"], 20.0)
        self.assertGreater(macros["calories"], 300.0)

    def test_gram_and_volume_scaling(self):
        """Verify weight (e.g. 200g, 150g) and volume (e.g. 500ml) scale accurately against base units."""
        subagent = MealAnalysisSubAgent()
        result = subagent.execute_tool(
            "parse_text_meal_macros",
            raw_text="200g chicken breast, 150g grilled salmon, 500ml milk",
            meal_type="dinner",
        )
        self.assertTrue(result.success)
        items = result.data["meal_log"]["items"]
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["quantity"], 2.0)
        self.assertEqual(items[0]["macros"]["calories"], 330.0)
        self.assertEqual(items[0]["macros"]["protein_g"], 62.0)
        self.assertEqual(items[1]["quantity"], 1.5)
        self.assertEqual(items[1]["macros"]["calories"], 312.0)
        self.assertEqual(items[1]["macros"]["protein_g"], 30.6)
        self.assertEqual(items[2]["quantity"], 2.0)
        self.assertEqual(items[2]["macros"]["calories"], 240.0)

    def test_meal_analysis_subagent_image_logging(self):
        """Verify analyze_meal_image_macros tool detects meal items from image identifier."""
        subagent = MealAnalysisSubAgent()
        result = subagent.execute_tool(
            "analyze_meal_image_macros",
            image_path_or_url="salmon_bowl_lunch.jpg",
            meal_type="lunch",
        )
        self.assertTrue(result.success)
        meal_log = result.data["meal_log"]
        self.assertEqual(meal_log["input_type"], "image")
        macros = meal_log["total_macros"]
        self.assertGreaterEqual(macros["protein_g"], 40.0)

    def test_tool_error_recovery_instructions(self):
        """Verify tool execution returns structured recovery instructions on invalid arguments."""
        subagent = MealAnalysisSubAgent()
        # Pass empty raw_text which triggers validation error inside tool function
        result = subagent.execute_tool(
            "parse_text_meal_macros",
            raw_text="",
            meal_type="breakfast",
        )
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertTrue("EXECUTION_ERROR" in result.error.error_code or "INVALID_INPUT_SCHEMA" in result.error.error_code)
        self.assertIn("recovery_instructions", result.error.model_dump())
        self.assertGreater(len(result.error.recovery_instructions), 10)

    def test_daily_report_subagent_report_generation(self):
        """Verify DailyReportAgent computes daily totals, compliance score, and markdown report."""
        root = HealthTrackerRootAgent()
        # Log breakfast and lunch
        root.log_meal_text("3 scrambled eggs, 2 sourdough toast, 1/2 avocado", meal_type=MealType.BREAKFAST)
        root.log_meal_text("200g chicken breast, 1 cup cooked rice, 1 cup steamed broccoli", meal_type=MealType.LUNCH)

        report_res = root.generate_daily_report()
        self.assertTrue(report_res["success"])
        report = report_res["report"]
        self.assertEqual(report["total_meals_logged"], 2)
        self.assertGreaterEqual(report["consumed_macros"]["protein_g"], 60.0)
        self.assertGreater(report["goal_compliance_score"], 0)
        self.assertIn("Daily Health & Fitness Report", report["report_markdown"])


if __name__ == '__main__':
    unittest.main()
