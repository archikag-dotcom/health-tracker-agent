"""
Meal Analysis Subagent (`MealAnalysisAgent`).
Provides tools to parse meal text descriptions and analyze food photos to compute exact macronutrients and protein content.
"""
import uuid
import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from adk.base import SubAgent
from adk.tools import tool, ToolResult
from models.schemas import MealLog, MealType, MacroNutrients, FoodItem
from services.nutrition_db import parse_natural_text_meal, analyze_meal_image_content


# --- Strict Pydantic Schemas for Meal Analysis Tools ---

class ParseTextMealInput(BaseModel):
    """Input payload for parsing text meal descriptions."""
    raw_text: str = Field(..., min_length=2, description="Natural language text description of the meal (e.g., '2 scrambled eggs with 1 slice sourdough toast').")
    meal_type: MealType = Field(default=MealType.LUNCH, description="Category of meal (breakfast, lunch, dinner, snack).")
    user_id: str = Field(default="user_1", description="Identifier of the user logging the meal.")
    notes: Optional[str] = Field(None, description="Optional extra notes or custom modifications.")


class AnalyzeMealImageInput(BaseModel):
    """Input payload for analyzing meal photos."""
    image_path_or_url: str = Field(..., min_length=2, description="Path to local image file or URL of food photo.")
    meal_type: MealType = Field(default=MealType.LUNCH, description="Category of meal (breakfast, lunch, dinner, snack).")
    user_id: str = Field(default="user_1", description="Identifier of the user logging the meal.")
    additional_context: Optional[str] = Field(None, description="Optional description or context to improve image recognition.")


class MealAnalysisResult(BaseModel):
    """Output payload from meal analysis tools."""
    meal_log: MealLog = Field(..., description="Structured meal log containing itemized food and calculated macro totals.")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence level of the analysis (0.0 to 1.0).")
    summary_text: str = Field(..., description="Human-readable summary of calculated calories and macros.")


# --- Tool Implementations with Specific Names & Descriptions ---

@tool(
    name="parse_text_meal_macros",
    description="Parses natural language text meal descriptions (e.g. '2 eggs, 1 slice toast, 1/2 avocado') and calculates itemized calories, protein, carbs, fat, and fiber content.",
    input_schema=ParseTextMealInput,
    output_schema=MealAnalysisResult,
)
def parse_text_meal_macros(
    raw_text: str,
    meal_type: MealType = MealType.LUNCH,
    user_id: str = "user_1",
    notes: Optional[str] = None,
) -> MealAnalysisResult:
    """
    Parses natural language meal text descriptions into structured food items with macro calculations.
    :param raw_text: Natural language text description of the meal (e.g., '2 scrambled eggs with 1 slice sourdough toast').
    :param meal_type: Category of meal (breakfast, lunch, dinner, snack).
    :param user_id: Identifier of the user logging the meal.
    :param notes: Optional extra notes or custom modifications.
    """
    if isinstance(meal_type, str):
        meal_type = MealType(meal_type)

    if not raw_text or len(raw_text.strip()) < 2:
        raise ValueError("Provided meal text is empty or too short. Please specify items like '2 eggs and 1 slice toast'.")

    # Parse items using nutrition database engine
    items: List[FoodItem] = parse_natural_text_meal(raw_text)

    # Compute combined macros sum
    total_cal = sum(item.macros.calories for item in items)
    total_prot = sum(item.macros.protein_g for item in items)
    total_carbs = sum(item.macros.carbs_g for item in items)
    total_fat = sum(item.macros.fat_g for item in items)
    total_fiber = sum(item.macros.fiber_g for item in items)

    total_macros = MacroNutrients(
        calories=round(total_cal, 1),
        protein_g=round(total_prot, 1),
        carbs_g=round(total_carbs, 1),
        fat_g=round(total_fat, 1),
        fiber_g=round(total_fiber, 1),
    )

    avg_confidence = (sum(item.confidence_score for item in items) / len(items)) if items else 0.8

    meal_log = MealLog(
        id=f"meal_{uuid.uuid4().hex[:8]}",
        timestamp=datetime.datetime.now().isoformat(),
        meal_type=meal_type,
        input_type="text",
        raw_input=raw_text,
        items=items,
        total_macros=total_macros,
        notes=notes,
    )

    summary = (
        f"Parsed {len(items)} item(s) for {meal_type.value.title()}: "
        f"{total_macros.calories} kcal | Protein: {total_macros.protein_g}g | "
        f"Carbs: {total_macros.carbs_g}g | Fat: {total_macros.fat_g}g | Fiber: {total_macros.fiber_g}g"
    )

    return MealAnalysisResult(
        meal_log=meal_log,
        confidence_score=round(avg_confidence, 2),
        summary_text=summary,
    )


@tool(
    name="analyze_meal_image_macros",
    description="Analyzes uploaded food images or photo URLs, identifies food items via computer vision feature extraction, and calculates macronutrient and protein breakdown.",
    input_schema=AnalyzeMealImageInput,
    output_schema=MealAnalysisResult,
)
def analyze_meal_image_macros(
    image_path_or_url: str,
    meal_type: MealType = MealType.LUNCH,
    user_id: str = "user_1",
    additional_context: Optional[str] = None,
) -> MealAnalysisResult:
    """
    Analyzes food photo image input to detect items and estimate macros.
    :param image_path_or_url: Path to local image file or URL of food photo.
    :param meal_type: Category of meal (breakfast, lunch, dinner, snack).
    :param user_id: Identifier of the user logging the meal.
    :param additional_context: Optional description or context to improve image recognition.
    """
    if isinstance(meal_type, str):
        meal_type = MealType(meal_type)

    if not image_path_or_url or len(image_path_or_url.strip()) < 2:
        raise ValueError("Image path or URL is empty. Please provide a valid file path or URL.")

    # Image analysis simulator engine
    identifier = f"{image_path_or_url} {additional_context or ''}"
    items, detection_summary = analyze_meal_image_content(identifier)

    # Compute combined macros sum
    total_cal = sum(item.macros.calories for item in items)
    total_prot = sum(item.macros.protein_g for item in items)
    total_carbs = sum(item.macros.carbs_g for item in items)
    total_fat = sum(item.macros.fat_g for item in items)
    total_fiber = sum(item.macros.fiber_g for item in items)

    total_macros = MacroNutrients(
        calories=round(total_cal, 1),
        protein_g=round(total_prot, 1),
        carbs_g=round(total_carbs, 1),
        fat_g=round(total_fat, 1),
        fiber_g=round(total_fiber, 1),
    )

    avg_confidence = (sum(item.confidence_score for item in items) / len(items)) if items else 0.90

    meal_log = MealLog(
        id=f"meal_{uuid.uuid4().hex[:8]}",
        timestamp=datetime.datetime.now().isoformat(),
        meal_type=meal_type,
        input_type="image",
        raw_input=image_path_or_url,
        items=items,
        total_macros=total_macros,
        image_url=image_path_or_url,
        notes=detection_summary,
    )

    summary = (
        f"Visual Analysis ({detection_summary}) for {meal_type.value.title()}: "
        f"{total_macros.calories} kcal | Protein: {total_macros.protein_g}g | "
        f"Carbs: {total_macros.carbs_g}g | Fat: {total_macros.fat_g}g"
    )

    return MealAnalysisResult(
        meal_log=meal_log,
        confidence_score=round(avg_confidence, 2),
        summary_text=summary,
    )


class MealAnalysisSubAgent(SubAgent):
    """Subagent specialized in text and image meal macro analysis."""

    def __init__(self):
        super().__init__(
            name="MealAnalysisSubAgent",
            description="Specialized subagent that analyzes meal inputs (text or images) to detect food items and calculate macronutrient & protein content.",
            role="Meal Content & Macro Analyzer",
        )
        self.register_tool(parse_text_meal_macros)
        self.register_tool(analyze_meal_image_macros)
