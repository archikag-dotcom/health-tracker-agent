"""
Unit tests for Constitution, Context Bloat Management, Vector Memory Bank, and Async Consolidation.
"""
import unittest
import time
from adk.constitution import AgentConstitution, DEFAULT_CONSTITUTION
from adk.context import ContextManager
from services.vector_memory import PersistentVectorMemoryBank
from services.async_memory import AsyncMemoryConsolidator
from agents.root_agent import HealthTrackerRootAgent
from models.schemas import MealType


class TestMemoryAndConstitution(unittest.TestCase):

    def test_agent_constitution(self):
        """Verify Agent Constitution provides explicit persona, domain rules, and safety constraints."""
        constitution = AgentConstitution()
        prompt = constitution.get_system_prompt()
        self.assertIn("NutriAgent", prompt)
        self.assertIn("Human macronutrient metabolism", prompt)
        self.assertIn("Strict Schema Validation", prompt)
        self.assertIn("Safety Disclaimer", prompt)

    def test_context_manager_compaction(self):
        """Verify sliding window context compaction when memory items exceed token budget."""
        manager = ContextManager(max_token_budget=100, max_history_turns=3)
        
        # Create 10 sample meal items
        items = [
            {"id": f"item_{i}", "total_macros": {"calories": 300.0, "protein_g": 25.0}}
            for i in range(10)
        ]
        
        res = manager.compact_items(items)
        stats = res["stats"]
        
        self.assertTrue(stats["is_compacted"])
        self.assertEqual(len(res["compacted_items"]), 3)
        self.assertIn("COMPACTED CONTEXT SUMMARY", res["summary"])

    def test_vector_memory_bank(self):
        """Verify persistent vector store indexing and semantic similarity search."""
        memory = PersistentVectorMemoryBank(storage_path="data/test_vector_store.json")
        
        memory.add_document("doc_1", "Grilled chicken breast with brown rice and steamed broccoli")
        memory.add_document("doc_2", "Whey protein smoothie with banana and peanut butter")
        memory.add_document("doc_3", "Pan seared salmon fillet with quinoa and avocado")
        
        results = memory.search_similar("chicken breast broccoli", top_k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].doc_id, "doc_1")
        self.assertGreater(results[0].similarity_score, 0.3)

    def test_async_memory_consolidation(self):
        """Verify non-blocking background dispatch of memory vector indexing."""
        root_agent = HealthTrackerRootAgent()
        initial_stats = AsyncMemoryConsolidator.get_stats()
        
        # Log text meal (dispatches background vector indexing)
        res = root_agent.log_meal_text("3 eggs, 2 slices toast", meal_type=MealType.BREAKFAST)
        self.assertTrue(res["success"])
        
        # Wait briefly for background thread worker
        time.sleep(0.05)
        new_stats = AsyncMemoryConsolidator.get_stats()
        
        self.assertGreaterEqual(new_stats["completed_background_tasks"], initial_stats["completed_background_tasks"])


if __name__ == "__main__":
    unittest.main()
