
"""
CloudQA AI Tester - Main CLI

Pipeline:
Natural Language
    -> Groq Test Planner
    -> Structured TestPlan
    -> User Confirmation
    -> Selenium Browser Execution
    -> PASS / FAIL Report

Usage:
    python main.py --url https://example.com \
        --test "Verify Example Domain is displayed"

    python main.py --url https://example.com \
        --test "Verify Example Domain is displayed" --yes

    python main.py --url https://example.com \
        --test "Verify Example Domain is displayed" --dry-run
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from browser_engine import BrowserEngine
from groq_planner import GroqPlanner
from locator_engine import LocatorEngine
from executor import TestExecutor


# =============================================================
# CONFIGURATION
# =============================================================

DEFAULT_TIMEOUT = 15
DEFAULT_REPORT_DIR = "reports"
DEFAULT_SCREENSHOT_DIR = "screenshots"


# =============================================================
# CLI ARGUMENTS
# =============================================================

def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "AI-powered browser testing using "
            "Groq, Selenium and semantic element resolution."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--url",
        required=True,
        help="Target website URL.",
    )

    parser.add_argument(
        "--test",
        required=True,
        help=(
            "Natural-language test case. "
            'Example: "Verify the login page is displayed".'
        ),
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome without displaying the browser window.",
    )

    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Execute the generated test plan without confirmation.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and display a test plan without executing it.",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Default browser and element timeout in seconds.",
    )

    parser.add_argument(
        "--model",
        default=None,
        help="Groq model override. Defaults to GROQ_MODEL in .env.",
    )

    parser.add_argument(
        "--report-dir",
        default=DEFAULT_REPORT_DIR,
        help="Directory for JSON test reports.",
    )

    parser.add_argument(
        "--screenshot-dir",
        default=DEFAULT_SCREENSHOT_DIR,
        help="Directory for browser screenshots.",
    )

    return parser.parse_args()


# =============================================================
# DISPLAY HELPERS
# =============================================================

def print_banner():
    print("\n" + "=" * 68)
    print("             CLOUDQA AI-POWERED TEST AUTOMATION")
    print("=" * 68)
    print("  Natural Language | Groq | Selenium | Semantic Locators")
    print("=" * 68)


def print_test_information(args):
    print("\nTARGET CONFIGURATION")
    print("-" * 68)
    print(f"Website:       {args.url}")
    print(f"Test case:     {args.test}")
    print(f"Headless:      {args.headless}")
    print(f"Timeout:       {args.timeout}s")
    print(f"Execution:     {'Dry run' if args.dry_run else 'Live'}")
    print("-" * 68)


def display_plan(plan):
    print("\n" + "=" * 68)
    print("                 GENERATED TEST PLAN")
    print("=" * 68)

    print(f"\nTest name: {plan.test_name}")
    print(f"Description: {plan.description}")
    print(f"Number of steps: {len(plan.steps)}")

    print("\nSTEPS")
    print("-" * 68)

    for index, step in enumerate(plan.steps, start=1):
        print(f"\n{index}. ACTION: {step.action.value.upper()}")

        if step.element_description:
            print(f"   Element: {step.element_description}")

        if step.value is not None:
            # Do not print credential values.
            if "{{" in step.value and "}}" in step.value:
                print("   Value: [ENVIRONMENT VARIABLE]")
            else:
                print(f"   Value: {step.value}")

        if step.expected_text:
            print(f"   Expected text: {step.expected_text}")

        if step.expected_url:
            print(f"   Expected URL: {step.expected_url}")

        if step.reasoning:
            print(f"   Reasoning: {step.reasoning}")

    print("\n" + "=" * 68)


def confirm_execution() -> bool:
    print("\nReview the generated plan before execution.")

    try:
        response = input(
            "Execute this test? [Y/n]: "
        ).strip().lower()

        return response in {"", "y", "yes"}

    except EOFError:
        return False


# =============================================================
# REPORT MANAGEMENT
# =============================================================

def create_report_filename(test_name: str) -> str:
    slug = re.sub(
        r"[^a-zA-Z0-9]+",
        "_",
        test_name.strip().lower(),
    ).strip("_")

    slug = slug[:50] or "browser_test"

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    return f"{slug}_{timestamp}.json"


def save_report(
    report,
    plan,
    url: str,
    report_dir: str,
) -> Path:

    output_directory = Path(report_dir)
    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = create_report_filename(
        report.test_name
    )

    output_path = output_directory / filename

    report_data = {
        "metadata": {
            "generated_at": datetime.now().astimezone().isoformat(),
            "target_url": url,
            "test_name": report.test_name,
            "status": report.status,
        },
        "test_plan": plan.model_dump(mode="json"),
        "execution_report": report.model_dump(mode="json"),
    }

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report_data,
            file,
            indent=4,
            ensure_ascii=False,
        )

    return output_path


# =============================================================
# APPLICATION PIPELINE
# =============================================================

def run_application(args) -> int:
    browser = None

    try:
        # -----------------------------------------------------
        # STEP 1: Start browser
        # -----------------------------------------------------

        print("\n[1/5] Starting browser...")

        browser = BrowserEngine(
            headless=args.headless,
            timeout=args.timeout,
            screenshot_dir=args.screenshot_dir,
        )

        browser.start()

        print("[OK] Browser started.")

        # -----------------------------------------------------
        # STEP 2: Open target website
        # -----------------------------------------------------

        print("\n[2/5] Opening target website...")

        browser.open(args.url)

        print(f"[OK] Page title: {browser.page_title()}")
        print(f"[OK] Current URL: {browser.current_url()}")

        # -----------------------------------------------------
        # STEP 3: Inspect DOM and generate plan
        # -----------------------------------------------------

        print("\n[3/5] Inspecting page and generating test plan...")

        page_snapshot = browser.get_page_snapshot()

        print("[OK] DOM snapshot captured.")

        planner = GroqPlanner(
            model=args.model,
        )

        plan = planner.generate_plan(
            test_case=args.test,
            url=args.url,
            page_snapshot=page_snapshot,
        )

        print("[OK] Groq generated a valid test plan.")

        display_plan(plan)

        # -----------------------------------------------------
        # STEP 4: Confirmation / dry run
        # -----------------------------------------------------

        if args.dry_run:
            print("\n[DRY RUN] Test plan generated successfully.")
            print("[DRY RUN] Browser interactions were not executed.")
            return 0

        if not args.yes:
            if not confirm_execution():
                print("\nExecution cancelled by user.")
                return 0

        # -----------------------------------------------------
        # STEP 5: Execute plan
        # -----------------------------------------------------

        print("\n[4/5] Initializing semantic locator engine...")

        locator = LocatorEngine(browser)

        print("[OK] Locator engine ready.")

        print("\n[5/5] Executing test plan...")

        executor = TestExecutor(
            browser=browser,
            locator_engine=locator,
            screenshot_dir=args.screenshot_dir,
        )

        report = executor.execute(plan)

        # -----------------------------------------------------
        # Save report
        # -----------------------------------------------------

        report_path = save_report(
            report=report,
            plan=plan,
            url=args.url,
            report_dir=args.report_dir,
        )

        print("\nREPORT SAVED")
        print("-" * 68)
        print(f"File: {report_path.resolve()}")
        print(f"Status: {report.status}")
        print("-" * 68)

        # Exit code:
        # 0 = all tests passed
        # 1 = test execution failed
        return 0 if report.status == "PASS" else 1

    except KeyboardInterrupt:
        print("\n\nExecution interrupted by user.")
        return 130

    except Exception as exc:
        print("\n" + "=" * 68)
        print("APPLICATION ERROR")
        print("=" * 68)
        print(f"{type(exc).__name__}: {exc}")
        print("=" * 68)

        return 2

    finally:
        if browser is not None:
            try:
                browser.close()
                print("\n[OK] Browser closed.")
            except Exception as exc:
                print(f"\n[WARNING] Browser cleanup failed: {exc}")


# =============================================================
# ENTRY POINT
# =============================================================

def main():
    args = parse_arguments()

    if args.timeout < 1 or args.timeout > 120:
        print("Error: timeout must be between 1 and 120 seconds.")
        return 2

    if not args.url.startswith(("http://", "https://")):
        print("Error: URL must start with http:// or https://.")
        return 2

    if not args.test.strip():
        print("Error: test description cannot be empty.")
        return 2

    print_banner()
    print_test_information(args)

    return run_application(args)


if __name__ == "__main__":
    sys.exit(main())
