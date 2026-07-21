"""
CLI Interface for Python ADK Health Tracker Agent.
Allows command-line meal logging, image macro analysis, and daily report generation.
"""
import sys
import argparse
import datetime
from models.schemas import MealType, FitnessGoal, UserProfile
from agents.root_agent import HealthTrackerRootAgent

root_agent = HealthTrackerRootAgent()


def main():
    parser = argparse.ArgumentParser(description="Health Tracker Agent CLI (Python ADK)")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: log-text
    text_parser = subparsers.add_parser("log-text", help="Log a meal using natural language text input")
    text_parser.add_argument("text", type=str, help="Text description of meal (e.g., '2 eggs, 1 slice toast')")
    text_parser.add_argument("--type", type=str, default="lunch", choices=["breakfast", "lunch", "dinner", "snack"], help="Meal category")
    text_parser.add_argument("--date", type=str, default=datetime.date.today().isoformat(), help="Date (YYYY-MM-DD)")

    # Command: log-image
    image_parser = subparsers.add_parser("log-image", help="Log a meal using food photo image path")
    image_parser.add_argument("image_path", type=str, help="Path or filename of meal photo")
    image_parser.add_argument("--type", type=str, default="lunch", choices=["breakfast", "lunch", "dinner", "snack"], help="Meal category")
    image_parser.add_argument("--date", type=str, default=datetime.date.today().isoformat(), help="Date (YYYY-MM-DD)")

    # Command: report
    report_parser = subparsers.add_parser("report", help="Generate comprehensive daily report and macro breakdown")
    report_parser.add_argument("--date", type=str, default=datetime.date.today().isoformat(), help="Date (YYYY-MM-DD)")

    # Command: profile
    profile_parser = subparsers.add_parser("profile", help="Show user profile and daily target macros")

    # Command: eval
    eval_parser = subparsers.add_parser("eval", help="Run static regression evaluation harness against golden dataset")
    eval_parser.add_argument("--threshold", type=float, default=5.0, help="Maximum allowed MAPE percentage threshold")

    # Command: agentapi
    agentapi_parser = subparsers.add_parser("agentapi", help="Agent API CLI subcommand wrapper")
    agentapi_parser.add_argument("action", choices=["new-conversation", "send-message"], help="Agent API action")
    agentapi_parser.add_argument("prompt_or_msg", type=str, help="Prompt or message content")
    agentapi_parser.add_argument("--recipient", type=str, default=None, help="Recipient ID for send-message")

    args = parser.parse_args()

    if args.command == "log-text":
        res = root_agent.log_meal_text(
            raw_text=args.text,
            meal_type=MealType(args.type),
            date_str=args.date,
        )
        if res.get("success"):
            print("\n✅ Meal Logged Successfully!")
            print(f"Summary: {res['summary']}")
            print(f"Confidence Score: {res['confidence_score'] * 100}%")
        else:
            print(f"\n❌ Error logging text meal: {res.get('error')}")

    elif args.command == "log-image":
        res = root_agent.log_meal_image(
            image_path_or_url=args.image_path,
            meal_type=MealType(args.type),
            date_str=args.date,
        )
        if res.get("success"):
            print("\n📸 Image Meal Analyzed Successfully!")
            print(f"Summary: {res['summary']}")
            print(f"Confidence Score: {res['confidence_score'] * 100}%")
        else:
            print(f"\n❌ Error logging image meal: {res.get('error')}")

    elif args.command == "report":
        res = root_agent.generate_daily_report(date_str=args.date)
        if res.get("success"):
            report = res["report"]
            print("\n=======================================================")
            print(f"📊 DAILY HEALTH & FITNESS REPORT ({report['date']})")
            print("=======================================================")
            print(report["report_markdown"])
        else:
            print(f"\n❌ Error generating report: {res.get('error')}")

    elif args.command == "profile":
        p = root_agent.user_profile
        print(f"\n👤 User Profile: {p.name} ({p.age}y, {p.weight_kg}kg, Goal: {p.fitness_goal.value.title()})")
        print(f"🎯 Targets -> Calories: {p.daily_calories_target} kcal | Protein: {p.daily_protein_target_g}g | Carbs: {p.daily_carbs_target_g}g | Fat: {p.daily_fat_target_g}g")

    elif args.command == "eval":
        from tests.eval_harness import RegressionEvalHarness
        harness = RegressionEvalHarness()
        metrics = harness.run_eval(max_allowed_mape=args.threshold)
        import json
        print("\n=======================================================")
        print("🧪 GOLDEN DATASET STATIC REGRESSION EVALUATION HARNESS")
        print("=======================================================")
        print(json.dumps(metrics.model_dump(), indent=2))
        if metrics.passed_threshold:
            print("\n✅ REGRESSION EVALUATION PASSED! Overall MAPE is within threshold.")
        else:
            print("\n❌ REGRESSION EVALUATION FAILED! Overall MAPE exceeds threshold.")

    elif args.command == "agentapi":
        import subprocess
        if args.action == "new-conversation":
            cmd = ["agentapi", "new-conversation", args.prompt_or_msg]
        else:
            cmd = ["agentapi", "send-message", args.recipient or "self", args.prompt_or_msg]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            print(f"\nAgent API Output:\n{res.stdout or res.stderr}")
        except Exception as e:
            print(f"\nAgent API Invocation simulated: {cmd} -> {str(e)}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
