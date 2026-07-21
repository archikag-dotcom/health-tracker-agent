"""
Dynamic Model Router.
Routes specific tasks to the most appropriate LLM tier (Flash for speed, Pro for reasoning/planning).
"""
from enum import Enum
from typing import Dict, Any
from pydantic import BaseModel, Field


class ModelTier(str, Enum):
    FLASH_LITE = "gemini-2.5-flash-lite"
    FLASH = "gemini-2.5-flash"
    PRO = "gemini-2.5-pro"


class TaskRoute(BaseModel):
    task_name: str
    selected_tier: ModelTier
    rationale: str
    temperature: float = 0.2


class ModelRouter:
    """Intelligent Model Router mapping task complexity to optimal LLM model tier."""

    @staticmethod
    def route_task(task_name: str, is_planning: bool = False, requires_vision: bool = False) -> TaskRoute:
        """Determines best model tier for given task parameters."""
        task_lower = task_name.lower()

        if is_planning or "report" in task_lower or "strategy" in task_lower or "self_eval" in task_lower:
            return TaskRoute(
                task_name=task_name,
                selected_tier=ModelTier.PRO,
                rationale="Task involves multi-step reasoning, goal compliance evaluation, or daily report planning.",
                temperature=0.3,
            )
        elif requires_vision or "image" in task_lower or "photo" in task_lower:
            return TaskRoute(
                task_name=task_name,
                selected_tier=ModelTier.FLASH,
                rationale="Task requires visual feature extraction and image food recognition.",
                temperature=0.1,
            )
        else:
            return TaskRoute(
                task_name=task_name,
                selected_tier=ModelTier.FLASH_LITE,
                rationale="Task is a lightweight structured text parse or macro database lookup.",
                temperature=0.0,
            )
