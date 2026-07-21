"""
Static Regression Evaluation Harness.
Measures agent performance against golden dataset benchmarks to detect quality or macro regression.
"""
import os
import json
from typing import Dict, List, Any
from pydantic import BaseModel, Field
from agents.meal_analysis_agent import MealAnalysisSubAgent


class RegressionMetrics(BaseModel):
    total_test_cases: int
    passed_cases: int
    failed_cases: int
    overall_mape_pct: float
    calorie_mape_pct: float
    protein_mape_pct: float
    passed_threshold: bool
    details: List[Dict[str, Any]] = Field(default_factory=list)


class RegressionEvalHarness:
    """Evaluation Harness for benchmark regression testing against golden dataset."""

    def __init__(self, golden_dataset_path: str = "tests/golden_dataset.json"):
        self.golden_dataset_path = golden_dataset_path
        self.agent = MealAnalysisSubAgent()

    def run_eval(self, max_allowed_mape: float = 5.0) -> RegressionMetrics:
        """Executes golden benchmark test cases and calculates MAPE macro regression scores."""
        if not os.path.exists(self.golden_dataset_path):
            raise FileNotFoundError(f"Golden dataset not found at {self.golden_dataset_path}")

        with open(self.golden_dataset_path, "r") as f:
            cases = json.load(f)

        total_cases = len(cases)
        passed_cases = 0
        failed_cases = 0
        
        cal_errors: List[float] = []
        prot_errors: List[float] = []
        details: List[Dict[str, Any]] = []

        for case in cases:
            case_id = case["id"]
            raw_input = case["input_raw"]
            meal_type = case["meal_type"]
            expected = case["expected_macros"]

            res = self.agent.execute_tool(
                "parse_text_meal_macros",
                raw_text=raw_input,
                meal_type=meal_type,
            )

            if not res.success or not res.data:
                failed_cases += 1
                details.append({
                    "id": case_id,
                    "status": "FAIL",
                    "reason": "Agent tool execution failed.",
                })
                continue

            actual = res.data["meal_log"]["total_macros"]

            # Calculate Absolute Percentage Error (APE)
            cal_err = abs(actual["calories"] - expected["calories"]) / max(1.0, expected["calories"]) * 100.0
            prot_err = abs(actual["protein_g"] - expected["protein_g"]) / max(1.0, expected["protein_g"]) * 100.0

            cal_errors.append(cal_err)
            prot_errors.append(prot_err)

            case_passed = cal_err <= case["max_allowed_error_pct"] and prot_err <= case["max_allowed_error_pct"]
            if case_passed:
                passed_cases += 1
            else:
                failed_cases += 1

            details.append({
                "id": case_id,
                "input": raw_input,
                "status": "PASS" if case_passed else "FAIL",
                "calorie_error_pct": round(cal_err, 2),
                "protein_error_pct": round(prot_err, 2),
                "expected": expected,
                "actual": actual,
            })

        mean_cal_mape = sum(cal_errors) / len(cal_errors) if cal_errors else 0.0
        mean_prot_mape = sum(prot_errors) / len(prot_errors) if prot_errors else 0.0
        overall_mape = (mean_cal_mape + mean_prot_mape) / 2.0

        return RegressionMetrics(
            total_test_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            overall_mape_pct=round(overall_mape, 2),
            calorie_mape_pct=round(mean_cal_mape, 2),
            protein_mape_pct=round(mean_prot_mape, 2),
            passed_threshold=overall_mape <= max_allowed_mape,
            details=details,
        )


if __name__ == "__main__":
    harness = RegressionEvalHarness()
    metrics = harness.run_eval()
    print(json.dumps(metrics.model_dump(), indent=2))
