"""
Agent Design Patterns Module.
Implements Coordinator and Sequential design patterns for multi-agent workflows.
"""
from typing import List, Dict, Any, Callable
from pydantic import BaseModel, Field


class WorkflowStepResult(BaseModel):
    step_name: str
    subagent_name: str
    success: bool
    output: Dict[str, Any]


class CoordinatorPattern:
    """Coordinator Design Pattern for distributing subagent tasks and consolidating results."""

    def __init__(self, name: str = "RootCoordinator"):
        self.name = name

    def coordinate_execution(
        self,
        tasks: List[Dict[str, Any]],
        executor_func: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Distributes tasks across registered subagents and aggregates execution output."""
        results: List[WorkflowStepResult] = []
        all_successful = True

        for task in tasks:
            step_name = task.get("step_name", "subagent_task")
            subagent = task.get("subagent", "unknown")
            
            res = executor_func(task)
            success = res.get("success", False)
            if not success:
                all_successful = False

            results.append(
                WorkflowStepResult(
                    step_name=step_name,
                    subagent_name=subagent,
                    success=success,
                    output=res,
                )
            )

        return {
            "coordinator": self.name,
            "overall_success": all_successful,
            "completed_steps": len(results),
            "step_results": [r.model_dump() for r in results],
        }


class SequentialPattern:
    """Sequential Design Pattern for executing linear subagent pipelines with state passing."""

    def __init__(self, name: str = "SequentialPipeline"):
        self.name = name

    def execute_pipeline(
        self,
        initial_state: Dict[str, Any],
        pipeline_steps: List[Callable[[Dict[str, Any]], Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Executes pipeline steps in strict linear order, passing mutated state forward."""
        current_state = initial_state.copy()
        history: List[Dict[str, Any]] = []

        for idx, step_fn in enumerate(pipeline_steps, 1):
            res = step_fn(current_state)
            if not res.get("success", True):
                return {
                    "pipeline": self.name,
                    "success": False,
                    "failed_step_index": idx,
                    "error": res.get("error"),
                    "final_state": current_state,
                    "history": history,
                }
            
            # Merge state forward
            if "state_update" in res:
                current_state.update(res["state_update"])
            history.append({"step": idx, "output": res})

        return {
            "pipeline": self.name,
            "success": True,
            "final_state": current_state,
            "completed_steps": len(pipeline_steps),
            "history": history,
        }
