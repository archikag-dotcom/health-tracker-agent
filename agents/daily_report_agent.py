"""
Daily Report Subagent (`DailyReportAgent`).
Provides tools to aggregate daily caloric/macro intake, calculate goal compliance, and build formatted health & fitness reports.
"""
import uuid
from typing import List, Dict
from pydantic import BaseModel, Field

from adk.base import SubAgent
from adk.tools import tool
from models.schemas import (
    MealLog,
    UserProfile,
    MacroNutrients,
    MacroRatio,
    DailyReport,
)


# --- Strict Input & Output Schemas for Daily Report Tools ---

class CalculateDailyTotalsInput(BaseModel):
    """Input schema for calculating daily macronutrient totals."""
    logged_meals: List[MealLog] = Field(..., description="List of all meals logged for the specified day.")
    user_profile: UserProfile = Field(..., description="User profile containing target calorie and macro goals.")
    date: str = Field(..., description="Date of the report in YYYY-MM-DD format.")


class DailyTotalsResult(BaseModel):
    """Output schema for daily macro totals calculation."""
    date: str = Field(..., description="Date of evaluation.")
    consumed_macros: MacroNutrients = Field(..., description="Total macros consumed across all logged meals.")
    target_macros: MacroNutrients = Field(..., description="Daily target macros based on user profile goals.")
    remaining_macros: MacroNutrients = Field(..., description="Remaining macro budget (target minus consumed).")
    macro_ratios: MacroRatio = Field(..., description="Caloric macro ratio percentage breakdown (Protein / Carbs / Fat).")
    protein_compliance_pct: float = Field(..., description="Percentage of protein goal achieved.")
    calorie_compliance_pct: float = Field(..., description="Percentage of calorie goal consumed.")


class GenerateDailyReportInput(BaseModel):
    """Input schema for daily report generation tool."""
    date: str = Field(..., description="Date string in YYYY-MM-DD format.")
    logged_meals: List[MealLog] = Field(..., description="List of meal logs for the given day.")
    user_profile: UserProfile = Field(..., description="User profile with targets and fitness goal settings.")


# --- Helper Calculation Functions ---

def _compute_ratios(macros: MacroNutrients) -> MacroRatio:
    """Calculates macro percentage ratios of total caloric intake."""
    prot_cal = macros.protein_g * 4.0
    carbs_cal = macros.carbs_g * 4.0
    fat_cal = macros.fat_g * 9.0
    total_cal = prot_cal + carbs_cal + fat_cal

    if total_cal <= 0:
        return MacroRatio(protein_pct=0.0, carbs_pct=0.0, fat_pct=0.0)

    return MacroRatio(
        protein_pct=round((prot_cal / total_cal) * 100.0, 1),
        carbs_pct=round((carbs_cal / total_cal) * 100.0, 1),
        fat_pct=round((fat_cal / total_cal) * 100.0, 1),
    )


# --- Tool Implementations ---

@tool(
    name="calculate_daily_macro_totals",
    description="Aggregates all meals logged throughout the day, computes total calories, protein, carbs, fat, and fiber, and compares them against target goals.",
    input_schema=CalculateDailyTotalsInput,
    output_schema=DailyTotalsResult,
)
def calculate_daily_macro_totals(
    logged_meals: List[MealLog],
    user_profile: UserProfile,
    date: str,
) -> DailyTotalsResult:
    """
    Aggregates daily macronutrient totals from logged meals and evaluates target compliance.
    :param logged_meals: List of all meals logged for the specified day.
    :param user_profile: User profile containing target calorie and macro goals.
    :param date: Date of the report in YYYY-MM-DD format.
    """
    if isinstance(user_profile, dict):
        user_profile = UserProfile(**user_profile)

    if not logged_meals:
        # If no meals logged, return zeros with guidance note
        zero_macros = MacroNutrients(calories=0, protein_g=0, carbs_g=0, fat_g=0, fiber_g=0)
        target_macros = MacroNutrients(
            calories=user_profile.daily_calories_target,
            protein_g=user_profile.daily_protein_target_g,
            carbs_g=user_profile.daily_carbs_target_g,
            fat_g=user_profile.daily_fat_target_g,
            fiber_g=user_profile.daily_fiber_target_g,
        )
        return DailyTotalsResult(
            date=date,
            consumed_macros=zero_macros,
            target_macros=target_macros,
            remaining_macros=target_macros,
            macro_ratios=MacroRatio(protein_pct=0.0, carbs_pct=0.0, fat_pct=0.0),
            protein_compliance_pct=0.0,
            calorie_compliance_pct=0.0,
        )

    # Coerce dictionary meals into MealLog Pydantic instances
    parsed_meals: List[MealLog] = [
        MealLog(**m) if isinstance(m, dict) else m for m in logged_meals
    ]

    # Sum consumed values
    tot_cal = sum(m.total_macros.calories for m in parsed_meals)
    tot_prot = sum(m.total_macros.protein_g for m in parsed_meals)
    tot_carbs = sum(m.total_macros.carbs_g for m in parsed_meals)
    tot_fat = sum(m.total_macros.fat_g for m in parsed_meals)
    tot_fiber = sum(m.total_macros.fiber_g for m in parsed_meals)

    consumed = MacroNutrients(
        calories=round(tot_cal, 1),
        protein_g=round(tot_prot, 1),
        carbs_g=round(tot_carbs, 1),
        fat_g=round(tot_fat, 1),
        fiber_g=round(tot_fiber, 1),
    )

    targets = MacroNutrients(
        calories=user_profile.daily_calories_target,
        protein_g=user_profile.daily_protein_target_g,
        carbs_g=user_profile.daily_carbs_target_g,
        fat_g=user_profile.daily_fat_target_g,
        fiber_g=user_profile.daily_fiber_target_g,
    )

    remaining = MacroNutrients(
        calories=round(targets.calories - consumed.calories, 1),
        protein_g=round(targets.protein_g - consumed.protein_g, 1),
        carbs_g=round(targets.carbs_g - consumed.carbs_g, 1),
        fat_g=round(targets.fat_g - consumed.fat_g, 1),
        fiber_g=round(targets.fiber_g - consumed.fiber_g, 1),
    )

    ratios = _compute_ratios(consumed)

    prot_comp = round((consumed.protein_g / targets.protein_g) * 100.0, 1) if targets.protein_g > 0 else 0.0
    cal_comp = round((consumed.calories / targets.calories) * 100.0, 1) if targets.calories > 0 else 0.0

    return DailyTotalsResult(
        date=date,
        consumed_macros=consumed,
        target_macros=targets,
        remaining_macros=remaining,
        macro_ratios=ratios,
        protein_compliance_pct=prot_comp,
        calorie_compliance_pct=cal_comp,
    )


@tool(
    name="generate_daily_nutrition_report",
    description="Generates a comprehensive daily health and fitness report formatted with nutritional insights, protein distribution across meals, goal compliance score, and formatted markdown summary.",
    input_schema=GenerateDailyReportInput,
    output_schema=DailyReport,
)
def generate_daily_nutrition_report(
    date: str,
    logged_meals: List[MealLog],
    user_profile: UserProfile,
) -> DailyReport:
    """
    Generates a full daily health report evaluating macro goals, protein distribution, and insights.
    :param date: Date string in YYYY-MM-DD format.
    :param logged_meals: List of meal logs for the given day.
    :param user_profile: User profile with targets and fitness goal settings.
    """
    if isinstance(user_profile, dict):
        user_profile = UserProfile(**user_profile)

    parsed_meals: List[MealLog] = [
        MealLog(**m) if isinstance(m, dict) else m for m in logged_meals
    ]

    totals = calculate_daily_macro_totals(logged_meals=parsed_meals, user_profile=user_profile, date=date)
    consumed = totals.consumed_macros
    targets = totals.target_macros
    remaining = totals.remaining_macros

    # Calculate protein distribution per meal type
    protein_dist: Dict[str, float] = {"breakfast": 0.0, "lunch": 0.0, "dinner": 0.0, "snack": 0.0}
    for m in parsed_meals:
        protein_dist[m.meal_type.value] = round(protein_dist.get(m.meal_type.value, 0.0) + m.total_macros.protein_g, 1)

    # Compute overall compliance score out of 100
    # Weighted: 45% protein target, 40% calorie target, 15% fiber target
    prot_score = min(totals.protein_compliance_pct, 100.0)
    # Calorie score penalizes overshooting or severe under-eating
    cal_diff = abs(100.0 - totals.calorie_compliance_pct)
    cal_score = max(0.0, 100.0 - cal_diff)
    fiber_score = min((consumed.fiber_g / max(targets.fiber_g, 1.0)) * 100.0, 100.0)

    overall_score = round((prot_score * 0.45) + (cal_score * 0.40) + (fiber_score * 0.15), 1)

    # Generate insights recommendations
    insights: List[str] = []
    if totals.protein_compliance_pct >= 90.0:
        insights.append(f"💪 Excellent protein intake! You hit {totals.protein_compliance_pct}% of your {user_profile.daily_protein_target_g}g daily goal.")
    else:
        insights.append(f"⚡ Protein deficit detected. You need {max(0.0, remaining.protein_g)}g more protein to meet your target of {user_profile.daily_protein_target_g}g.")

    if abs(remaining.calories) <= 150:
        insights.append(f"🎯 Caloric intake is well-aligned with your target of {targets.calories} kcal ({totals.calorie_compliance_pct}%).")
    elif remaining.calories > 150:
        insights.append(f"🍏 You have a deficit remaining of {remaining.calories} kcal for today.")
    else:
        insights.append(f"⚠️ Caloric intake exceeded target by {abs(remaining.calories)} kcal.")

    if consumed.fiber_g >= targets.fiber_g:
        insights.append(f"🥗 High fiber goal met ({consumed.fiber_g}g consumed), supporting gut health and satiety.")
    else:
        insights.append(f"🌱 Consider adding leafy greens, chia seeds, or berries to reach {targets.fiber_g}g of fiber.")

    # Check protein timing (spikes across meals)
    meals_with_20g_protein = sum(1 for p in protein_dist.values() if p >= 20.0)
    if meals_with_20g_protein >= 3:
        insights.append("✨ Great protein distribution! You achieved muscle protein synthesis (20g+ protein) across 3+ meals.")
    else:
        insights.append("💡 Tip: Try distributing protein evenly across meals (25g-35g per meal) for optimal muscle recovery.")

    # Build Markdown Report Output
    md_report = f"""# 📊 Daily Health & Fitness Report - {date}
**User**: {user_profile.name} | **Goal**: {user_profile.fitness_goal.value.title()} | **Compliance Score**: {overall_score}/100

---

## 🎯 Macronutrient Summary
| Metric | Consumed | Daily Target | Remaining | Compliance |
| :--- | :--- | :--- | :--- | :--- |
| **Calories** | `{consumed.calories} kcal` | `{targets.calories} kcal` | `{remaining.calories} kcal` | `{totals.calorie_compliance_pct}%` |
| **Protein** | `{consumed.protein_g}g` | `{targets.protein_g}g` | `{remaining.protein_g}g` | `{totals.protein_compliance_pct}%` |
| **Carbs** | `{consumed.carbs_g}g` | `{targets.carbs_g}g` | `{remaining.carbs_g}g` | `{round((consumed.carbs_g/targets.carbs_g)*100, 1) if targets.carbs_g else 0}%` |
| **Fats** | `{consumed.fat_g}g` | `{targets.fat_g}g` | `{remaining.fat_g}g` | `{round((consumed.fat_g/targets.fat_g)*100, 1) if targets.fat_g else 0}%` |
| **Fiber** | `{consumed.fiber_g}g` | `{targets.fiber_g}g` | `{remaining.fiber_g}g` | `{round((consumed.fiber_g/targets.fiber_g)*100, 1) if targets.fiber_g else 0}%` |

### 🥗 Macro Caloric Split
- **Protein**: `{totals.macro_ratios.protein_pct}%` of total calories
- **Carbohydrates**: `{totals.macro_ratios.carbs_pct}%` of total calories
- **Fat**: `{totals.macro_ratios.fat_pct}%` of total calories

---

## 🍗 Protein Distribution by Meal
- 🌅 **Breakfast**: `{protein_dist['breakfast']}g` protein
- ☀️ **Lunch**: `{protein_dist['lunch']}g` protein
- 🌙 **Dinner**: `{protein_dist['dinner']}g` protein
- 🍏 **Snacks**: `{protein_dist['snack']}g` protein

---

## 📝 Logged Meals ({len(logged_meals)} Meals)
"""
    for idx, meal in enumerate(parsed_meals, 1):
        md_report += f"\n### {idx}. {meal.meal_type.value.title()} ({meal.total_macros.calories} kcal)\n"
        md_report += f"- **Input**: `{meal.raw_input}`\n"
        md_report += f"- **Macros**: P: `{meal.total_macros.protein_g}g` | C: `{meal.total_macros.carbs_g}g` | F: `{meal.total_macros.fat_g}g` | Fiber: `{meal.total_macros.fiber_g}g`\n"
        md_report += "- **Items Detected**:\n"
        for item in meal.items:
            md_report += f"  - {item.quantity} {item.unit} **{item.name}** ({item.macros.calories} kcal, {item.macros.protein_g}g protein)\n"

    md_report += "\n---\n\n## 💡 Agent Nutritional Insights & Recommendations\n"
    for insight in insights:
        md_report += f"- {insight}\n"

    return DailyReport(
        report_id=f"rep_{uuid.uuid4().hex[:8]}",
        date=date,
        user_profile=user_profile,
        total_meals_logged=len(parsed_meals),
        logged_meals=parsed_meals,
        consumed_macros=consumed,
        target_macros=targets,
        remaining_macros=remaining,
        macro_ratios=totals.macro_ratios,
        goal_compliance_score=overall_score,
        protein_compliance_pct=totals.protein_compliance_pct,
        calorie_compliance_pct=totals.calorie_compliance_pct,
        protein_distribution_by_meal=protein_dist,
        nutritional_insights=insights,
        report_markdown=md_report,
    )


class DailyReportSubAgent(SubAgent):
    """Subagent specialized in calculating daily totals and generating nutrition reports."""

    def __init__(self):
        super().__init__(
            name="DailyReportSubAgent",
            description="Specialized subagent that aggregates daily macronutrients, compares against targets, and generates daily health breakdown reports.",
            role="Daily Macro & Report Calculator",
        )
        self.register_tool(calculate_daily_macro_totals)
        self.register_tool(generate_daily_nutrition_report)
