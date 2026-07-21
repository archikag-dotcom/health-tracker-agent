"""
FastAPI Server for Python ADK Health Tracker Agent.
Provides REST API endpoints and static file serving for the Web Application.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datetime
from typing import Optional, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

from models.schemas import UserProfile, MealType, FitnessGoal
from agents.root_agent import HealthTrackerRootAgent

app = FastAPI(
    title="Health Tracker Agent - Python ADK",
    description="Multi-agent health tracker system with Meal Analysis and Daily Report Subagents.",
    version="1.0.0",
)

# Global root agent instance
root_agent = HealthTrackerRootAgent()

# Ensure uploads directory exists
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# --- REST API Pydantic Request Payload Schemas ---

class LogTextMealRequest(BaseModel):
    raw_text: str = Field(..., description="Natural text meal description (e.g. '2 eggs and sourdough toast').")
    meal_type: str = Field(default="lunch", description="Meal category: breakfast, lunch, dinner, snack.")
    date_str: Optional[str] = Field(None, description="Date YYYY-MM-DD.")
    notes: Optional[str] = Field(None, description="Optional extra notes.")


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    fitness_goal: Optional[FitnessGoal] = None
    daily_calories_target: Optional[float] = None
    daily_protein_target_g: Optional[float] = None
    daily_carbs_target_g: Optional[float] = None
    daily_fat_target_g: Optional[float] = None
    daily_fiber_target_g: Optional[float] = None


# --- REST Endpoints ---

@app.get("/api/profile")
def get_profile():
    """Returns current user profile and target macro goals."""
    return root_agent.user_profile.model_dump()


@app.post("/api/profile")
def update_profile(req: UpdateProfileRequest):
    """Updates user profile and fitness targets."""
    p = root_agent.user_profile
    if req.name: p.name = req.name
    if req.age: p.age = req.age
    if req.weight_kg: p.weight_kg = req.weight_kg
    if req.height_cm: p.height_cm = req.height_cm
    if req.fitness_goal: p.fitness_goal = req.fitness_goal
    if req.daily_calories_target: p.daily_calories_target = req.daily_calories_target
    if req.daily_protein_target_g: p.daily_protein_target_g = req.daily_protein_target_g
    if req.daily_carbs_target_g: p.daily_carbs_target_g = req.daily_carbs_target_g
    if req.daily_fat_target_g: p.daily_fat_target_g = req.daily_fat_target_g
    if req.daily_fiber_target_g: p.daily_fiber_target_g = req.daily_fiber_target_g
    return {"success": True, "profile": p.model_dump()}


@app.post("/api/meals/log-text")
def log_text_meal(req: LogTextMealRequest):
    """Delegates natural text meal logging to MealAnalysisSubAgent."""
    try:
        meal_type_enum = MealType(req.meal_type.lower())
    except ValueError:
        meal_type_enum = MealType.LUNCH

    res = root_agent.log_meal_text(
        raw_text=req.raw_text,
        meal_type=meal_type_enum,
        date_str=req.date_str,
        notes=req.notes,
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.post("/api/meals/log-image")
async def log_image_meal(
    file: UploadFile = File(...),
    meal_type: str = Form("lunch"),
    date_str: Optional[str] = Form(None),
    additional_context: Optional[str] = Form(None),
):
    """Saves uploaded meal image and delegates visual macro analysis to MealAnalysisSubAgent."""
    try:
        meal_type_enum = MealType(meal_type.lower())
    except ValueError:
        meal_type_enum = MealType.LUNCH

    # Save uploaded file locally using basename
    safe_filename = os.path.basename(file.filename)
    filename = f"{int(datetime.datetime.now().timestamp())}_{safe_filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    res = root_agent.log_meal_image(
        image_path_or_url=file_path,
        meal_type=meal_type_enum,
        date_str=date_str,
        additional_context=additional_context or file.filename,
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.get("/api/meals")
def get_logged_meals(date: Optional[str] = None):
    """Returns all logged meals for a specific date."""
    date_key = date or datetime.date.today().isoformat()
    meals = root_agent.meal_logs_by_date.get(date_key, [])
    return {
        "date": date_key,
        "count": len(meals),
        "meals": [m.model_dump() for m in meals],
    }


@app.delete("/api/meals/{meal_id}")
def delete_meal(meal_id: str, date: Optional[str] = None):
    """Deletes a logged meal."""
    deleted = root_agent.delete_meal(meal_id, date_str=date)
    return {"success": deleted}


@app.get("/api/reports/daily")
def get_daily_report(date: Optional[str] = None):
    """Generates daily nutrition report via RootAgent and DailyReportSubAgent."""
    res = root_agent.generate_daily_report(date_str=date)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


class ConfirmActionRequest(BaseModel):
    token_id: str = Field(..., description="Human confirmation token ID.")


@app.post("/api/actions/clear-history")
def request_clear_history(token_id: Optional[str] = None):
    """High-stakes endpoint: Requires explicit human confirmation token before deleting history."""
    return root_agent.request_clear_all_history(confirmed_token=token_id)


@app.post("/api/actions/confirm")
def confirm_action(req: ConfirmActionRequest):
    """Confirms pending high-stakes action token."""
    return root_agent.request_clear_all_history(confirmed_token=req.token_id)


@app.post("/api/actions/reset-app")
def reset_app():
    """Resets the entire application state back to fresh clean defaults."""
    root_agent.reset_app_state()
    # Clean uploaded image files
    if os.path.exists(UPLOAD_DIR):
        for filename in os.listdir(UPLOAD_DIR):
            file_p = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(file_p):
                try:
                    os.remove(file_p)
                except Exception:
                    pass
    return {"success": True, "message": "App reset to clean fresh state."}


# Mount uploads and static web interface
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def read_root():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return "<h1>Health Tracker Agent API</h1><p>Web dashboard static files initializing...</p>"
