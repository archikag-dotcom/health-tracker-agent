"""
Async Memory Consolidator.
Offloads expensive vector embeddings and memory indexing to background executor threads.
"""
import concurrent.futures
import time
from typing import Dict, Any, Optional
from services.vector_memory import PersistentVectorMemoryBank

# Shared ThreadPoolExecutor for non-blocking background consolidation
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="adk_memory_worker")
_VECTOR_BANK = PersistentVectorMemoryBank()

_TASKS_COMPLETED = 0


def _background_index_meal(meal_dict: Dict[str, Any]):
    """Background thread function for indexing a meal into vector store."""
    global _TASKS_COMPLETED
    time.sleep(0.01)  # Simulate non-blocking async background workload
    
    meal_id = meal_dict.get("id", "meal_unknown")
    meal_type = meal_dict.get("meal_type", "meal")
    raw_input = meal_dict.get("raw_input", "")
    items_text = ", ".join([f"{it['quantity']} {it['name']}" for it in meal_dict.get("items", [])])
    
    content = f"Meal {meal_type}: {raw_input}. Detected items: {items_text}. Total calories: {meal_dict.get('total_macros', {}).get('calories')} kcal, protein: {meal_dict.get('total_macros', {}).get('protein_g')}g."
    
    _VECTOR_BANK.add_document(
        doc_id=f"vec_{meal_id}",
        content=content,
        metadata={
            "category": "meal_log",
            "meal_type": meal_type,
            "date": meal_dict.get("timestamp", "").split("T")[0],
        }
    )
    _TASKS_COMPLETED += 1


def _background_index_report(report_dict: Dict[str, Any]):
    """Background thread function for indexing daily health reports."""
    global _TASKS_COMPLETED
    time.sleep(0.01)
    
    rep_id = report_dict.get("report_id", "rep_unknown")
    date_str = report_dict.get("date", "")
    score = report_dict.get("goal_compliance_score", 0.0)
    insights_text = " ".join(report_dict.get("nutritional_insights", []))
    
    content = f"Daily Report {date_str}: Goal Compliance Score {score}/100. Insights: {insights_text}"
    
    _VECTOR_BANK.add_document(
        doc_id=f"vec_{rep_id}",
        content=content,
        metadata={
            "category": "daily_report",
            "date": date_str,
            "compliance_score": score,
        }
    )
    _TASKS_COMPLETED += 1


class AsyncMemoryConsolidator:
    """Dispatches background tasks for memory consolidation and vector indexing."""

    @staticmethod
    def dispatch_meal_consolidation(meal_dict: Dict[str, Any]):
        """Dispatches non-blocking background meal vector indexing."""
        _EXECUTOR.submit(_background_index_meal, meal_dict)

    @staticmethod
    def dispatch_report_consolidation(report_dict: Dict[str, Any]):
        """Dispatches non-blocking background report vector indexing."""
        _EXECUTOR.submit(_background_index_report, report_dict)

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        return {
            "completed_background_tasks": _TASKS_COMPLETED,
            "indexed_vector_documents": len(_VECTOR_BANK.documents),
        }
