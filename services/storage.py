"""
Persistence Service.
Saves and loads user profile, meal logs, and daily targets to JSON disk storage.
"""
import os
import json
from typing import Dict, List, Any
from models.schemas import UserProfile, MealLog
from adk.logging import Redactor

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DATA_FILE = os.path.join(DATA_DIR, "health_data.json")


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_storage_data() -> Dict[str, Any]:
    """Loads profile and meal logs from JSON storage file."""
    ensure_data_dir()
    if not os.path.exists(DATA_FILE):
        return {"user_profile": UserProfile().model_dump(), "meal_logs_by_date": {}}

    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"user_profile": UserProfile().model_dump(), "meal_logs_by_date": {}}


def save_storage_data(user_profile: UserProfile, meal_logs_by_date: Dict[str, List[MealLog]]):
    """Saves profile and meal logs to JSON storage file after active PII scrubbing."""
    ensure_data_dir()
    data = {
        "user_profile": user_profile.model_dump(),
        "meal_logs_by_date": {
            date_str: [m.model_dump() for m in meals]
            for date_str, meals in meal_logs_by_date.items()
        },
    }
    scrubbed_data = Redactor.scrub_dict(data)
    with open(DATA_FILE, "w") as f:
        json.dump(scrubbed_data, f, indent=2)
