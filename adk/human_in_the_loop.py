"""
Human-in-the-Loop High-Stakes Action Manager.
Implements explicit code stops requiring human confirmation before high-stakes operations.
"""
import uuid
import time
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class PendingAction(BaseModel):
    token_id: str
    action_name: str
    description: str
    parameters: Dict[str, Any]
    created_at: float
    confirmed: bool = False


class HighStakesManager:
    """Manages high-stakes action gates requiring explicit human confirmation."""

    HIGH_STAKES_ACTIONS = [
        "DELETE_ALL_MEAL_LOGS",
        "SET_EXTREME_GOAL",
        "RESET_USER_PROFILE",
        "DELETE_MEAL_HISTORY",
    ]

    def __init__(self):
        self.pending_actions: Dict[str, PendingAction] = {}

    def is_high_stakes(self, action_name: str) -> bool:
        return action_name in self.HIGH_STAKES_ACTIONS

    def create_pending_confirmation(
        self, action_name: str, description: str, parameters: Dict[str, Any]
    ) -> PendingAction:
        """Creates a pending action token requiring human approval."""
        token_id = f"confirm_{uuid.uuid4().hex[:8]}"
        action = PendingAction(
            token_id=token_id,
            action_name=action_name,
            description=description,
            parameters=parameters,
            created_at=time.time(),
            confirmed=False,
        )
        self.pending_actions[token_id] = action
        return action

    def confirm_action(self, token_id: str) -> Optional[PendingAction]:
        """Approves and marks a pending high-stakes action as confirmed."""
        if token_id in self.pending_actions:
            action = self.pending_actions[token_id]
            action.confirmed = True
            return action
        return None

    def get_pending_actions(self) -> List[Dict[str, Any]]:
        """Returns active unconfirmed pending actions."""
        return [
            a.model_dump()
            for a in self.pending_actions.values()
            if not a.confirmed
        ]
