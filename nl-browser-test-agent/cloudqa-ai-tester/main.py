
import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from browser_engine import BrowserEngine
from executor import TestExecutor
from groq_planner import GroqPlanner
from locator_engine import LocatorEngine


def parse_args():
    parser = argparse.ArgumentParser(
        description="CloudQA AI Natural Language Browser Tester"
    )

    parser.add_argument("--url", required=True)
    parser.add_argument("--test", required=True)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout", type=int, default=15)

    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()

    browser = BrowserEngine(
        headless=not args.headed,
        timeout=args.timeout,
    )

    try:
        browser.start()
        browser.open(args.url)

        print(f"Page title: {browser.page_title()}")
        print(f"URL: {browser.current_url()}")

        snapshot = browser.snapshot()

        planner = GroqPlanner()
        plan = planner.generate_plan(
            user_test=args.test,
            page_snapshot=snapshot,
            page_url=browser.current_url(),
        )

        print("\nGenerated test plan:")
        print(json.dumps(
            plan.model_dump(mode="json"),
            indent=2,
        ))

        if not args.yes:
            confirmation = input(
                "\nExecute this plan? [y/N]: "
            ).strip().lower()

            if confirmation != "y":
                print("Execution cancelled.")
                return

        locator = LocatorEngine(
            browser=browser,
            timeout=args.timeout,
        )

        executor = TestExecutor(
            browser=browser,
            locator_engine=locator,
        )

        report = executor.execute(plan)

        Path("reports").mkdir(exist_ok=True)

        report_path = Path("reports/test_report.json")

        report_path.write_text(
            json.dumps(
                report.model_dump(mode="json"),
                indent=2,
            ),
            encoding="utf-8",
        )

        print(f"\nReport saved: {report_path.resolve()}")

        if report.status != "PASS":
            raise SystemExit(1)

    finally:
        browser.close()


if __name__ == "__main__":
    main()
