"""
Security & Evaluation Guardrails Module.
Implements input sanitization, output macro sanity checks, and self-reflection evaluation.
"""
import re
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class GuardrailResult(BaseModel):
    is_safe: bool
    guardrail_type: str
    violation_reason: Optional[str] = None
    self_eval_score: float = Field(100.0, description="Self-evaluation score 0-100.")
    sanitized_input: Optional[str] = None


class InputGuardrail:
    """Security Guardrail checking user text inputs for prompt injection or toxic content."""

    UNSAFE_PATTERNS = [
        r"ignore previous instructions",
        r"system prompt",
        r"sudo ",
        r"rm -rf",
        r"drop table",
        r"starve myself",
    ]

    @classmethod
    def evaluate(cls, user_input: str) -> GuardrailResult:
        input_lower = user_input.lower()
        for pattern in cls.UNSAFE_PATTERNS:
            if re.search(pattern, input_lower):
                return GuardrailResult(
                    is_safe=False,
                    guardrail_type="InputSecurity",
                    violation_reason=f"Input contains disallowed security pattern: '{pattern}'",
                    self_eval_score=0.0,
                )
        return GuardrailResult(
            is_safe=True,
            guardrail_type="InputSecurity",
            self_eval_score=100.0,
            sanitized_input=user_input.strip(),
        )


class OutputGuardrail:
    """Biological & Nutritional Output Sanity Guardrail."""

    MAX_MEAL_CALORIES = 3500.0
    MAX_MEAL_PROTEIN_G = 250.0

    @classmethod
    def evaluate_macros(cls, calories: float, protein_g: float) -> GuardrailResult:
        if calories < 0 or protein_g < 0:
            return GuardrailResult(
                is_safe=False,
                guardrail_type="OutputMacroSanity",
                violation_reason="Negative macronutrient values detected.",
                self_eval_score=0.0,
            )
        if calories > cls.MAX_MEAL_CALORIES:
            return GuardrailResult(
                is_safe=False,
                guardrail_type="OutputMacroSanity",
                violation_reason=f"Calculated meal calories ({calories} kcal) exceeds physiological single-meal ceiling ({cls.MAX_MEAL_CALORIES} kcal).",
                self_eval_score=20.0,
            )
        if protein_g > cls.MAX_MEAL_PROTEIN_G:
            return GuardrailResult(
                is_safe=False,
                guardrail_type="OutputMacroSanity",
                violation_reason=f"Calculated meal protein ({protein_g}g) exceeds realistic single-meal ceiling ({cls.MAX_MEAL_PROTEIN_G}g).",
                self_eval_score=20.0,
            )

        return GuardrailResult(
            is_safe=True,
            guardrail_type="OutputMacroSanity",
            self_eval_score=100.0,
        )


class SelfEvalGuardrail:
    """Self-Evaluation Guardrail measuring quality, completeness, and adherence of daily reports."""

    @classmethod
    def evaluate_report(cls, report_markdown: str, Total_meals: int) -> GuardrailResult:
        score = 100.0
        reasons: List[str] = []

        if Total_meals == 0:
            return GuardrailResult(
                is_safe=True,
                guardrail_type="SelfEvalReport",
                self_eval_score=50.0,
                violation_reason="Zero meals logged; report contains baseline targets only.",
            )

        if "Macronutrient Summary" not in report_markdown:
            score -= 30.0
            reasons.append("Missing Macronutrient Summary section.")

        if "Protein Distribution by Meal" not in report_markdown:
            score -= 30.0
            reasons.append("Missing Protein Distribution section.")

        if "Nutritional Insights" not in report_markdown:
            score -= 20.0
            reasons.append("Missing Nutritional Insights recommendations.")

        return GuardrailResult(
            is_safe=score >= 60.0,
            guardrail_type="SelfEvalReport",
            self_eval_score=score,
            violation_reason="; ".join(reasons) if reasons else None,
        )
