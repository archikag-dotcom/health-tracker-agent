"""
Context Bloat Management & Compaction Module.
Prevents context window bloat via token estimation, sliding windows, and automatic compaction.
"""
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ContextWindowStats(BaseModel):
    total_tokens: int
    max_token_budget: int
    item_count: int
    is_compacted: bool
    summary_snippet: Optional[str] = None


class ContextManager:
    """Manages token budgets, sliding window compaction, and automatic memory summarization."""

    def __init__(self, max_token_budget: int = 2500, max_history_turns: int = 10):
        self.max_token_budget = max_token_budget
        self.max_history_turns = max_history_turns

    @staticmethod
    def estimate_tokens(obj: Any) -> int:
        """Estimates token length of string or serialized object (approx 4 chars/token)."""
        if isinstance(obj, str):
            text = obj
        else:
            try:
                text = json.dumps(obj)
            except Exception:
                text = str(obj)
        return max(1, len(text) // 4)

    def compact_items(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Applies sliding window token compaction.
        If items exceed max_token_budget or max_history_turns, retains the most recent items
        and generates a high-level summary of older truncated items.
        """
        total_tokens = sum(self.estimate_tokens(item) for item in items)
        
        if total_tokens <= self.max_token_budget and len(items) <= self.max_history_turns:
            return {
                "compacted_items": items,
                "summary": None,
                "stats": ContextWindowStats(
                    total_tokens=total_tokens,
                    max_token_budget=self.max_token_budget,
                    item_count=len(items),
                    is_compacted=False,
                ).model_dump()
            }

        # Context exceeds budget: apply sliding window compaction
        recent_items = items[-self.max_history_turns:]
        older_items = items[:-self.max_history_turns]

        # Ensure recent items fit inside token budget
        while recent_items and sum(self.estimate_tokens(i) for i in recent_items) > self.max_token_budget:
            older_items.append(recent_items.pop(0))

        # Generate summary for older items
        older_summary = self._summarize_older_items(older_items)

        compacted_tokens = sum(self.estimate_tokens(i) for i in recent_items) + self.estimate_tokens(older_summary)

        return {
            "compacted_items": recent_items,
            "summary": older_summary,
            "stats": ContextWindowStats(
                total_tokens=compacted_tokens,
                max_token_budget=self.max_token_budget,
                item_count=len(recent_items),
                is_compacted=True,
                summary_snippet=older_summary[:100] + "..." if older_summary else None
            ).model_dump()
        }

    def _summarize_older_items(self, older_items: List[Dict[str, Any]]) -> str:
        """Consolidates older items into a dense context summary string."""
        if not older_items:
            return ""
        
        count = len(older_items)
        tot_calories = 0.0
        tot_protein = 0.0
        
        for item in older_items:
            if isinstance(item, dict):
                macros = item.get("total_macros", {})
                tot_calories += macros.get("calories", 0.0)
                tot_protein += macros.get("protein_g", 0.0)

        return f"[COMPACTED CONTEXT SUMMARY: Truncated {count} older entries totaling {tot_calories:.0f} kcal and {tot_protein:.1f}g protein to preserve token window budget.]"
