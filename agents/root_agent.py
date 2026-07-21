"""
Root Health Tracker Agent (`HealthTrackerRootAgent`).
Main orchestrator agent managing user sessions, meal logs storage, and subagent delegation.
"""
import datetime
from typing import List, Dict, Optional, Any
from adk.base import RootAgent
from models.schemas import UserProfile, MealLog, DailyReport, MealType
from agents.meal_analysis_agent import MealAnalysisSubAgent
from agents.daily_report_agent import DailyReportSubAgent


from services.storage import load_storage_data, save_storage_data
from services.vector_memory import PersistentVectorMemoryBank
from services.async_memory import AsyncMemoryConsolidator
from adk.patterns import CoordinatorPattern, SequentialPattern
from adk.router import ModelRouter
from adk.guardrails import InputGuardrail, OutputGuardrail, SelfEvalGuardrail
from adk.human_in_the_loop import HighStakesManager


class HealthTrackerRootAgent(RootAgent):
    """Root ADK Agent orchestrating subagents via Coordinator & Sequential design patterns."""

    def __init__(self, user_profile: Optional[UserProfile] = None):
        super().__init__(
            name="HealthTrackerRootAgent",
            description="Root Health Tracker Agent managing meal logging, macro calculations, and daily health report generation.",
        )
        # Register specialized subagents
        self.meal_analysis_subagent = MealAnalysisSubAgent()
        self.daily_report_subagent = DailyReportSubAgent()
        self.register_subagent(self.meal_analysis_subagent)
        self.register_subagent(self.daily_report_subagent)

        # ADK Engine Components
        self.vector_memory = PersistentVectorMemoryBank()
        self.coordinator = CoordinatorPattern(name="HealthTrackerCoordinator")
        self.sequential_pipeline = SequentialPattern(name="MealProcessingPipeline")
        self.router = ModelRouter()
        self.high_stakes_manager = HighStakesManager()

        # Load persisted data from storage
        storage_data = load_storage_data()
        self.user_profile = user_profile or UserProfile(**storage_data.get("user_profile", {}))
        
        self.meal_logs_by_date: Dict[str, List[MealLog]] = {}
        raw_logs = storage_data.get("meal_logs_by_date", {})
        for date_str, meals in raw_logs.items():
            self.meal_logs_by_date[date_str] = [MealLog(**m) if isinstance(m, dict) else m for m in meals]

    def _persist(self):
        save_storage_data(self.user_profile, self.meal_logs_by_date)

    def log_meal_text(
        self,
        raw_text: str,
        meal_type: MealType = MealType.LUNCH,
        date_str: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Processes text meal logging through Input Guardrails, Sequential Pipeline, Model Router, and Output Guardrails."""
        # Step 1: Input Guardrail Check
        input_eval = InputGuardrail.evaluate(raw_text)
        if not input_eval.is_safe:
            return {
                "success": False,
                "error": input_eval.violation_reason,
                "guardrail": input_eval.model_dump(),
            }

        safe_text = input_eval.sanitized_input or raw_text
        date_key = date_str or datetime.date.today().isoformat()

        # Step 2: Route model tier based on task
        route = self.router.route_task("parse_text_meal_macros")

        # Step 3: Semantic context search in memory bank
        similar_memories = self.vector_memory.search_similar(safe_text, top_k=2)

        # Step 4: Execute tool via MealAnalysisSubAgent
        result = self.meal_analysis_subagent.execute_tool(
            "parse_text_meal_macros",
            raw_text=safe_text,
            meal_type=meal_type.value if isinstance(meal_type, MealType) else meal_type,
            user_id=self.user_profile.user_id,
            notes=notes,
        )

        if not result.success or not result.data:
            return {
                "success": False,
                "error": result.error.model_dump() if result.error else "Failed to parse text meal",
            }

        meal_log_dict = result.data["meal_log"]
        meal_log = MealLog(**meal_log_dict)

        # Step 5: Output Macro Sanity Guardrail Check
        output_eval = OutputGuardrail.evaluate_macros(
            meal_log.total_macros.calories, meal_log.total_macros.protein_g
        )
        if not output_eval.is_safe:
            return {
                "success": False,
                "error": output_eval.violation_reason,
                "guardrail": output_eval.model_dump(),
            }

        if date_key not in self.meal_logs_by_date:
            self.meal_logs_by_date[date_key] = []
        self.meal_logs_by_date[date_key].append(meal_log)
        self._persist()

        # Async background consolidation
        AsyncMemoryConsolidator.dispatch_meal_consolidation(meal_log.model_dump())

        return {
            "success": True,
            "meal_log": meal_log.model_dump(),
            "summary": result.data["summary_text"],
            "confidence_score": result.data["confidence_score"],
            "model_route": route.model_dump(),
            "similar_past_meals": [m.content for m in similar_memories],
        }

    def log_meal_image(
        self,
        image_path_or_url: str,
        meal_type: MealType = MealType.LUNCH,
        date_str: Optional[str] = None,
        additional_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Processes image meal logging through Model Router (Flash Vision) and subagent tools."""
        date_key = date_str or datetime.date.today().isoformat()
        route = self.router.route_task("analyze_meal_image_macros", requires_vision=True)

        result = self.meal_analysis_subagent.execute_tool(
            "analyze_meal_image_macros",
            image_path_or_url=image_path_or_url,
            meal_type=meal_type.value if isinstance(meal_type, MealType) else meal_type,
            user_id=self.user_profile.user_id,
            additional_context=additional_context,
        )

        if not result.success or not result.data:
            return {
                "success": False,
                "error": result.error.model_dump() if result.error else "Failed to analyze image meal",
            }

        meal_log_dict = result.data["meal_log"]
        meal_log = MealLog(**meal_log_dict)

        if date_key not in self.meal_logs_by_date:
            self.meal_logs_by_date[date_key] = []
        self.meal_logs_by_date[date_key].append(meal_log)
        self._persist()

        # Async background consolidation
        AsyncMemoryConsolidator.dispatch_meal_consolidation(meal_log.model_dump())

        return {
            "success": True,
            "meal_log": meal_log.model_dump(),
            "summary": result.data["summary_text"],
            "confidence_score": result.data["confidence_score"],
            "model_route": route.model_dump(),
        }

    def generate_daily_report(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Routes daily report planning to Gemini Pro model tier and executes Self-Evaluation Guardrails."""
        date_key = date_str or datetime.date.today().isoformat()
        logged_meals = self.meal_logs_by_date.get(date_key, [])

        # Route to PRO model tier for planning and report evaluation
        route = self.router.route_task("generate_daily_nutrition_report", is_planning=True)

        # Context Bloat Compaction
        compacted_context = self.context_manager.compact_items([m.model_dump() for m in logged_meals])
        active_meals_data = compacted_context["compacted_items"]

        result = self.daily_report_subagent.execute_tool(
            "generate_daily_nutrition_report",
            date=date_key,
            logged_meals=active_meals_data,
            user_profile=self.user_profile.model_dump(),
        )

        if not result.success or not result.data:
            return {
                "success": False,
                "error": result.error.model_dump() if result.error else "Failed to generate report",
            }

        report = DailyReport(**result.data)

        # Self-Evaluation Guardrail Check
        self_eval = SelfEvalGuardrail.evaluate_report(report.report_markdown, len(active_meals_data))

        # Async background consolidation
        AsyncMemoryConsolidator.dispatch_report_consolidation(report.model_dump())

        return {
            "success": True,
            "report": report.model_dump(),
            "model_route": route.model_dump(),
            "self_eval_guardrail": self_eval.model_dump(),
            "context_stats": compacted_context["stats"],
        }

    def request_clear_all_history(self, confirmed_token: Optional[str] = None) -> Dict[str, Any]:
        """High-stakes action: Deletes all meal history. Requires explicit human confirmation token."""
        action_name = "DELETE_ALL_MEAL_LOGS"

        if not confirmed_token:
            # Create pending human confirmation token
            pending = self.high_stakes_manager.create_pending_confirmation(
                action_name=action_name,
                description="High-Stakes Request: Deleting all user meal history logs permanently.",
                parameters={},
            )
            return {
                "status": "NEEDS_CONFIRMATION",
                "requires_human_confirmation": True,
                "confirmation_token": pending.token_id,
                "message": f"HIGH-STAKES ACTION INTERCEPTED: Action '{action_name}' requires human approval. Pass token_id to confirm.",
            }

        # Check if human confirmation token is valid
        action = self.high_stakes_manager.confirm_action(confirmed_token)
        if not action or not action.confirmed:
            return {
                "status": "REJECTED",
                "error": "Invalid or unconfirmed confirmation token.",
            }

        # Execute high-stakes deletion after human approval
        self.meal_logs_by_date = {}
        self._persist()
        return {
            "status": "SUCCESS",
            "message": "All user meal history deleted successfully following human confirmation.",
        }

    def reset_app_state(self):
        """Clears all stored meal logs, resets user profile, and wipes storage files."""
        self.user_profile = UserProfile()
        self.meal_logs_by_date = {}
        self._persist()

    def delete_meal(self, meal_id: str, date_str: Optional[str] = None) -> bool:
        """Removes a logged meal by ID."""
        date_key = date_str or datetime.date.today().isoformat()
        if date_key in self.meal_logs_by_date:
            initial_len = len(self.meal_logs_by_date[date_key])
            self.meal_logs_by_date[date_key] = [m for m in self.meal_logs_by_date[date_key] if m.id != meal_id]
            if len(self.meal_logs_by_date[date_key]) < initial_len:
                self._persist()
                return True
        return False
