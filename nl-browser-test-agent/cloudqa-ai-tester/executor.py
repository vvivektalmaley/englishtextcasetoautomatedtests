
"""
CloudQA AI Tester - Test Executor

Executes validated TestPlans using Selenium and LocatorEngine.
Produces structured PASS/FAIL reports and failure screenshots.
"""

import os
import re
import time
from pathlib import Path
from typing import Optional

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.common.exceptions import (
    StaleElementReferenceException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
    TimeoutException,
    WebDriverException,
)

from schemas import (
    ActionType,
    TestPlan,
    TestStep,
    TestReport,
    StepResult,
)


class TestExecutor:
    """
    Executes a TestPlan step by step.

    Failure behavior:
        - Stops execution after the first failed step.
        - Captures a screenshot for the failed step.
        - Marks remaining steps SKIPPED.
        - Returns a structured TestReport.
    """

    def __init__(
        self,
        browser,
        locator_engine,
        screenshot_dir: str = "screenshots",
        assertion_poll_frequency: float = 0.3,
    ):
        self.browser = browser
        self.locator = locator_engine

        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.assertion_poll_frequency = assertion_poll_frequency

    # =========================================================
    # PUBLIC API
    # =========================================================

    def execute(
        self,
        plan: TestPlan,
        url: Optional[str] = None,
    ) -> TestReport:
        """
        Execute a TestPlan.

        Args:
            plan: Validated Pydantic TestPlan.
            url: Optional URL to open before executing.

        Returns:
            TestReport containing individual step results.
        """

        if url:
            self.browser.open(url)

        print("\n" + "=" * 65)
        print(f"TEST: {plan.test_name}")
        print(f"DESCRIPTION: {plan.description}")
        print(f"STEPS: {len(plan.steps)}")
        print("=" * 65)

        results = []
        passed_steps = 0
        failed_steps = 0
        failure_occurred = False

        for step_number, step in enumerate(plan.steps, start=1):

            if failure_occurred:
                results.append(
                    self._skipped_result(
                        step_number,
                        step,
                        "Skipped because an earlier step failed.",
                    )
                )
                continue

            result = self._execute_step(
                step_number,
                step,
            )

            results.append(result)

            if result.status == "PASS":
                passed_steps += 1

            elif result.status == "FAIL":
                failed_steps += 1
                failure_occurred = True

        overall_status = (
            "PASS"
            if failed_steps == 0
            else "FAIL"
        )

        report = TestReport(
            test_name=plan.test_name,
            status=overall_status,
            total_steps=len(plan.steps),
            passed_steps=passed_steps,
            failed_steps=failed_steps,
            results=results,
        )

        self._print_summary(report)

        return report

    # =========================================================
    # STEP EXECUTION
    # =========================================================

    def _execute_step(
        self,
        step_number: int,
        step: TestStep,
    ) -> StepResult:

        started = time.perf_counter()

        description = (
            step.element_description
            or step.expected_text
            or step.expected_url
            or step.action.value
        )

        print(
            f"\n[{step_number}] "
            f"{step.action.value.upper()} "
            f"- {description}"
        )

        try:
            self._perform_action(step)

            duration = time.perf_counter() - started

            result = StepResult(
                step_number=step_number,
                action=step.action.value,
                description=description,
                status="PASS",
                message="Step executed successfully.",
                duration_seconds=round(duration, 3),
            )

            self._print_step_result(result)

            return result

        except Exception as exc:

            duration = time.perf_counter() - started

            screenshot = self._capture_failure_screenshot(
                step_number
            )

            message = self._format_error(exc)

            result = StepResult(
                step_number=step_number,
                action=step.action.value,
                description=description,
                status="FAIL",
                message=message,
                duration_seconds=round(duration, 3),
                screenshot=screenshot,
            )

            self._print_step_result(result)

            return result

    def _perform_action(self, step: TestStep):
        action = step.action

        if action == ActionType.CLICK:
            self._click(step)

        elif action == ActionType.TYPE:
            self._type(step)

        elif action == ActionType.SELECT:
            self._select(step)

        elif action == ActionType.ASSERT_TEXT:
            self._assert_text(step)

        elif action == ActionType.ASSERT_URL:
            self._assert_url(step)

        elif action == ActionType.WAIT:
            self._wait(step)

        elif action == ActionType.PRESS_ENTER:
            self._press_enter(step)

        else:
            raise ValueError(
                f"Unsupported action: {action}"
            )

    # =========================================================
    # ACTIONS
    # =========================================================

    def _click(self, step: TestStep):
        self._require_description(step)

        match = self.locator.resolve(
            step.element_description,
            action="click",
            timeout=step.timeout_seconds,
        )

        self._retry_interaction(
            lambda: self._safe_click(match.element),
            step,
            action="click",
        )

    def _safe_click(self, element):
        self.locator.driver.execute_script(
            """
            arguments[0].scrollIntoView({
                block: 'center',
                inline: 'center'
            });
            """,
            element,
        )

        element.click()

    def _type(self, step: TestStep):
        self._require_description(step)

        if step.value is None:
            raise ValueError(
                "TYPE action requires a value."
            )

        value = self._resolve_environment_variables(
            step.value
        )

        def perform():
            match = self.locator.resolve(
                step.element_description,
                action="type",
                timeout=step.timeout_seconds,
            )

            element = match.element

            self.locator.driver.execute_script(
                """
                arguments[0].scrollIntoView({
                    block: 'center'
                });
                """,
                element,
            )

            element.click()
            element.clear()
            element.send_keys(value)

        self._retry_interaction(
            perform,
            step,
            action="type",
        )

    def _select(self, step: TestStep):
        self._require_description(step)

        if step.value is None:
            raise ValueError(
                "SELECT action requires a value."
            )

        value = self._resolve_environment_variables(
            step.value
        )

        def perform():
            match = self.locator.resolve(
                step.element_description,
                action="select",
                timeout=step.timeout_seconds,
            )

            element = match.element

            self.locator.driver.execute_script(
                """
                arguments[0].scrollIntoView({
                    block: 'center'
                });
                """,
                element,
            )

            dropdown = Select(element)

            try:
                dropdown.select_by_visible_text(value)

            except Exception:
                # Fallback: select by option value.
                dropdown.select_by_value(value)

        self._retry_interaction(
            perform,
            step,
            action="select",
        )

    def _press_enter(self, step: TestStep):
        self._require_description(step)

        def perform():
            match = self.locator.resolve(
                step.element_description,
                action="press_enter",
                timeout=step.timeout_seconds,
            )

            match.element.send_keys(Keys.ENTER)

        self._retry_interaction(
            perform,
            step,
            action="press_enter",
        )

    # =========================================================
    # ASSERTIONS
    # =========================================================

    def _assert_text(self, step: TestStep):
        if not step.expected_text:
            raise ValueError(
                "ASSERT_TEXT requires expected_text."
            )

        expected = self._resolve_environment_variables(
            step.expected_text
        ).strip()

        if not expected:
            raise ValueError(
                "Expected text cannot be empty."
            )

        def check(_driver):
            if step.element_description:
                try:
                    match = self.locator.resolve(
                        step.element_description,
                        action="assert_text",
                        timeout=1,
                    )

                    actual = match.element.text

                except Exception:
                    return False

            else:
                actual = self.locator.driver.execute_script(
                    """
                    return document.body
                        ? document.body.innerText
                        : '';
                    """
                )

            return expected.casefold() in actual.casefold()

        try:
            WebDriverWait(
                self.locator.driver,
                step.timeout_seconds,
                poll_frequency=self.assertion_poll_frequency,
            ).until(check)

        except TimeoutException as exc:
            raise AssertionError(
                f"Expected text '{expected}' "
                f"was not found within "
                f"{step.timeout_seconds} seconds."
            ) from exc

    def _assert_url(self, step: TestStep):
        if not step.expected_url:
            raise ValueError(
                "ASSERT_URL requires expected_url."
            )

        expected = self._resolve_environment_variables(
            step.expected_url
        ).strip()

        def check(_driver):
            current = self.browser.current_url

            return expected.casefold() in current.casefold()

        try:
            WebDriverWait(
                self.locator.driver,
                step.timeout_seconds,
                poll_frequency=self.assertion_poll_frequency,
            ).until(check)

        except TimeoutException as exc:
            raise AssertionError(
                f"Expected URL to contain '{expected}'. "
                f"Actual URL: {self.browser.current_url}"
            ) from exc

    def _wait(self, step: TestStep):
        """
        WAIT behavior:
        - If element_description exists, wait for it to resolve.
        - Otherwise wait for the requested duration in value.
        """

        if step.element_description:

            self.locator.resolve(
                step.element_description,
                action="wait",
                timeout=step.timeout_seconds,
            )

        else:
            duration = float(step.value or 1)

            if duration < 0 or duration > 60:
                raise ValueError(
                    "WAIT duration must be between "
                    "0 and 60 seconds."
                )

            time.sleep(duration)

    # =========================================================
    # INTERACTION RETRIES
    # =========================================================

    def _retry_interaction(
        self,
        operation,
        step: TestStep,
        action: str,
        retries: int = 2,
    ):
        """
        Retry interactions that fail due to stale elements
        or transient Selenium interaction errors.

        Each retry re-runs the operation and resolves the
        element again from the live DOM.
        """

        transient_errors = (
            StaleElementReferenceException,
            ElementClickInterceptedException,
            ElementNotInteractableException,
        )

        last_error = None

        for attempt in range(retries + 1):

            try:
                operation()
                return

            except transient_errors as exc:
                last_error = exc

                if attempt >= retries:
                    break

                print(
                    f"  Retrying {action} "
                    f"({attempt + 1}/{retries}) "
                    f"after {type(exc).__name__}"
                )

                time.sleep(0.5)

        if last_error:
            raise last_error

    # =========================================================
    # ENVIRONMENT VARIABLES
    # =========================================================

    def _resolve_environment_variables(
        self,
        value: str,
    ) -> str:
        """
        Resolve {{VARIABLE_NAME}} placeholders from environment.

        Example:
            {{CUSTOMER_EMAIL}}
            {{CUSTOMER_PASSWORD}}
        """

        pattern = r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}"

        def replace(match):
            variable = match.group(1)

            environment_value = os.getenv(variable)

            if environment_value is None:
                raise ValueError(
                    f"Missing environment variable: "
                    f"{variable}"
                )

            return environment_value

        return re.sub(pattern, replace, value)

    # =========================================================
    # VALIDATION / REPORTING
    # =========================================================

    def _require_description(self, step: TestStep):
        if not step.element_description:
            raise ValueError(
                f"{step.action.value} requires "
                f"element_description."
            )

    def _capture_failure_screenshot(
        self,
        step_number: int,
    ) -> Optional[str]:

        timestamp = time.strftime(
            "%Y%m%d_%H%M%S"
        )

        filename = (
            f"failure_step_{step_number}_"
            f"{timestamp}.png"
        )

        path = self.screenshot_dir / filename

        try:
            self.browser.screenshot(str(path))
            return str(path)

        except Exception as exc:
            print(
                f"  Screenshot capture failed: {exc}"
            )
            return None

    def _format_error(self, exc: Exception) -> str:
        message = str(exc).strip()

        if not message:
            message = type(exc).__name__

        return (
            f"{type(exc).__name__}: "
            f"{message[:1000]}"
        )

    def _skipped_result(
        self,
        step_number: int,
        step: TestStep,
        reason: str,
    ) -> StepResult:

        return StepResult(
            step_number=step_number,
            action=step.action.value,
            description=(
                step.element_description
                or step.expected_text
                or step.expected_url
                or step.action.value
            ),
            status="SKIPPED",
            message=reason,
            duration_seconds=0.0,
        )

    def _print_step_result(
        self,
        result: StepResult,
    ):
        print(
            f"  [{result.status}] "
            f"{result.message}"
        )

        if result.screenshot:
            print(
                f"  Screenshot: "
                f"{result.screenshot}"
            )

    def _print_summary(
        self,
        report: TestReport,
    ):
        print("\n" + "=" * 65)
        print("TEST SUMMARY")
        print("=" * 65)

        print(f"Test:       {report.test_name}")
        print(f"Status:     {report.status}")
        print(f"Total:      {report.total_steps}")
        print(f"Passed:     {report.passed_steps}")
        print(f"Failed:     {report.failed_steps}")
        print(
            f"Skipped:    "
            f"{sum(r.status == 'SKIPPED' for r in report.results)}"
        )

        print("-" * 65)

        for result in report.results:
            print(
                f"{result.step_number:02d} "
                f"{result.status:<8} "
                f"{result.action:<12} "
                f"{result.description}"
            )

        print("=" * 65)
