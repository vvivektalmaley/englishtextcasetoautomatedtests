
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    ElementNotInteractableException,
)


class BrowserEngine:
    """
    BrowserEngine: Main browser controller for the CloudQA AI test runner.

    It uses Selenium to control Google Chrome.

    Main responsibilities:
    1. Start and close Chrome.
    2. Open websites.
    3. Read webpage information.
    4. Identify interactive elements.
    5. Click buttons and fill forms.
    6. Select dropdown options.
    7. Capture screenshots.

    Example:
        browser = BrowserEngine()
        browser.start()
        browser.open("https://example.com")
        print(browser.page_title())
        browser.close()
    """

    # ---------------------------------------------------------
    # INITIALIZATION
    # ---------------------------------------------------------

    def __init__(
        self,
        headless: bool = False,
        timeout: int = 15,
        screenshot_dir: str = "screenshots",
    ):
        """
        PURPOSE:
            Initialize the BrowserEngine object.

        HOW IT WORKS:
            1. Stores whether Chrome should run visibly or in the background.
            2. Sets the maximum waiting time for browser operations.
            3. Initializes the driver as None because Chrome is not started yet.
            4. Creates a folder to store screenshots.

        PARAMETERS:
            headless:
                False = Chrome window is visible.
                True = Chrome runs in the background.

            timeout:
                Maximum time Selenium waits for an operation.

            screenshot_dir:
                Folder where screenshots will be saved.

        SAMPLE:
            browser = BrowserEngine(
                headless=False,
                timeout=20,
                screenshot_dir="my_screenshots"
            )

        RESULT:
            Creates a BrowserEngine object with the given settings.
            Chrome is not started until start() is called.
        """

        self.headless = headless
        self.timeout = timeout
        self.driver: WebDriver | None = None

        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # BROWSER LIFECYCLE
    # ---------------------------------------------------------

    def start(self) -> None:
        """
        PURPOSE:
            Start a new Google Chrome browser session.

        HOW IT WORKS:
            1. Checks whether a browser session already exists.
            2. Creates Chrome configuration options.
            3. Applies browser settings such as window size.
            4. Starts Chrome using Selenium WebDriver.
            5. Sets the maximum page-loading time.
            6. Handles errors if Chrome cannot start.

        SAMPLE:
            browser = BrowserEngine()
            browser.start()

        RESULT:
            Google Chrome opens and Selenium gets control of it.

        NOTE:
            Selenium Manager automatically handles ChromeDriver
            discovery and downloading when necessary.
        """

        # Avoid opening multiple Chrome sessions accidentally.
        if self.driver is not None:
            return

        options = Options()

        # Run Chrome without displaying its graphical window.
        if self.headless:
            options.add_argument("--headless=new")

        # Set the browser window dimensions.
        options.add_argument("--window-size=1440,1000")

        # Prevent notification popups.
        options.add_argument("--disable-notifications")

        # Disable popup blocking.
        options.add_argument("--disable-popup-blocking")

        # Allow Chrome to run in restricted environments.
        options.add_argument("--no-sandbox")

        # Reduce memory-related issues in some environments.
        options.add_argument("--disable-dev-shm-usage")

        try:
            # Launch Chrome and connect Selenium to it.
            self.driver = webdriver.Chrome(options=options)

            # Set the maximum page-loading time.
            self.driver.set_page_load_timeout(self.timeout)

        except WebDriverException as exc:
            raise RuntimeError(
                "Could not start Chrome. Ensure Chrome is installed "
                "and Selenium is installed in the active Python environment."
            ) from exc

    def close(self) -> None:
        """
        PURPOSE:
            Safely close the Chrome browser session.

        HOW IT WORKS:
            1. Checks whether Chrome is running.
            2. Calls driver.quit() to close all browser windows.
            3. Resets the driver variable to None.

        SAMPLE:
            browser.close()

        RESULT:
            Chrome closes and the browser session is released.

        WHY IMPORTANT:
            Prevents unnecessary background browser processes.
        """

        if self.driver is not None:
            try:
                self.driver.quit()
            finally:
                self.driver = None

    def __enter__(self) -> "BrowserEngine":
        """
        PURPOSE:
            Support Python's with statement.

        HOW IT WORKS:
            Python automatically calls __enter__() when
            entering a with block.

            This function starts Chrome and returns the
            BrowserEngine object.

        SAMPLE:
            with BrowserEngine() as browser:
                browser.open("https://example.com")

        RESULT:
            Chrome starts automatically when entering the block.
        """

        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """
        PURPOSE:
            Automatically close Chrome after a with block.

        HOW IT WORKS:
            Python calls this method when the with block ends,
            including when an exception occurs inside the block.

        SAMPLE:
            with BrowserEngine() as browser:
                browser.open("https://example.com")

            # Chrome closes automatically here.

        RESULT:
            Releases the browser session automatically.
        """

        self.close()

    # ---------------------------------------------------------
    # NAVIGATION
    # ---------------------------------------------------------

    def open(self, url: str) -> None:
        """
        PURPOSE:
            Open a website using Chrome.

        HOW IT WORKS:
            1. Checks whether the browser is running.
            2. Validates that the URL starts with HTTP or HTTPS.
            3. Uses driver.get() to navigate to the website.
            4. Waits until the document loading state is complete.

        SAMPLE:
            browser.open("https://www.google.com")

        RESULT:
            Chrome navigates to Google and waits for
            the document to finish loading.

        WHY IMPORTANT:
            The AI testing system needs the webpage loaded
            before it can inspect or interact with elements.
        """

        self._require_driver()

        # Reject invalid URL formats.
        if not url.startswith(("http://", "https://")):
            raise ValueError(
                "URL must start with http:// or https://"
            )

        # Navigate to the requested website.
        self.driver.get(url)

        # Wait until the browser reports document.readyState as complete.
        WebDriverWait(
            self.driver,
            self.timeout,
        ).until(
            lambda d: d.execute_script(
                "return document.readyState"
            ) == "complete"
        )

    def current_url(self) -> str:
        """
        PURPOSE:
            Get the URL of the currently opened webpage.

        HOW IT WORKS:
            Selenium reads the current_url property
            from the active Chrome browser.

        SAMPLE:
            url = browser.current_url()
            print(url)

        RESULT:
            Returns something like:
            https://www.google.com/
        """

        self._require_driver()
        return self.driver.current_url

    def page_title(self) -> str:
        """
        PURPOSE:
            Get the title of the currently opened webpage.

        HOW IT WORKS:
            Selenium reads the browser's document title.

        SAMPLE:
            title = browser.page_title()
            print(title)

        RESULT:
            Returns the webpage title as a string.
            Example: "Google"
        """

        self._require_driver()
        return self.driver.title

    def wait_for(
        self,
        locator: tuple[str, str],
        condition: str = "visible",
        timeout: int | None = None,
    ):
        """
        PURPOSE:
            Wait until a particular webpage element
            satisfies a specified condition.

        HOW IT WORKS:
            1. Receives an element locator.
            2. Creates a WebDriverWait object.
            3. Checks which condition was requested.
            4. Waits until that condition becomes true.
            5. Returns the matching webpage element.

        LOCATOR EXAMPLES:

            (By.ID, "email")
            (By.NAME, "password")
            (By.CSS_SELECTOR, "button[type='submit']")

        CONDITIONS:

            visible:
                Element exists and is visible.

            clickable:
                Element is visible and enabled for clicking.

            present:
                Element exists in the DOM.

        SAMPLE:
            email = browser.wait_for(
                (By.ID, "email"),
                condition="visible"
            )

        RESULT:
            Returns the matching Selenium WebElement.

        NOTE:
            If the condition is not satisfied before the
            timeout, Selenium raises TimeoutException.
        """

        self._require_driver()

        wait = WebDriverWait(
            self.driver,
            timeout or self.timeout,
        )

        # Wait until the element becomes visible.
        if condition == "visible":
            return wait.until(
                EC.visibility_of_element_located(locator)
            )

        # Wait until the element becomes clickable.
        if condition == "clickable":
            return wait.until(
                EC.element_to_be_clickable(locator)
            )

        # Wait until the element exists in the DOM.
        if condition == "present":
            return wait.until(
                EC.presence_of_element_located(locator)
            )

        # Reject unsupported conditions.
        raise ValueError(f"Unknown wait condition: {condition}")

    # ---------------------------------------------------------
    # DOM OBSERVATION
    # ---------------------------------------------------------

    def get_page_snapshot(
        self,
        max_elements: int = 250,
    ) -> dict[str, Any]:
        """
        PURPOSE:
            Collect information about the currently opened webpage.

            This is one of the most important functions
            for the CloudQA AI testing system.

        HOW IT WORKS:

            STEP 1:
                JavaScript selects interactive HTML elements
                such as buttons, inputs, links and dropdowns.

            STEP 2:
                A visibility function checks whether each
                element is displayed on the webpage.

            STEP 3:
                A label function extracts accessible labels
                from the elements.

            STEP 4:
                JavaScript collects information such as:
                    - HTML tag
                    - Element type
                    - Visible text
                    - Label
                    - Placeholder
                    - ID
                    - Name
                    - Current value
                    - Link URL
                    - Disabled status
                    - Required status
                    - Dropdown options
                    - Outer HTML

            STEP 5:
                Selenium executes the JavaScript inside Chrome.

            STEP 6:
                The extracted information is converted into
                a Python dictionary.

        SAMPLE:
            snapshot = browser.get_page_snapshot()

            print(snapshot["title"])
            print(snapshot["elements"])

        RESULT:
            Returns structured webpage information.

        WHY IMPORTANT:
            The AI can use this information to understand
            webpage elements before deciding what action
            to perform.

        IMPORTANT:
            This function only observes the webpage.
            It does not click buttons or modify form values.
        """

        self._require_driver()

        # JavaScript executed inside the currently opened webpage.
        script = """
        // STEP 1: Find interactive webpage elements.
        const nodes = Array.from(
            document.querySelectorAll(
                'input, button, select, textarea, a, [role], [contenteditable="true"]'
            )
        );

        // STEP 2: Check whether an element is visible.
        function visible(el) {
            const s = window.getComputedStyle(el);
            const r = el.getBoundingClientRect();

            return (
                s.display !== 'none' &&
                s.visibility !== 'hidden' &&
                r.width > 0 &&
                r.height > 0
            );
        }

        // STEP 3: Extract an accessible label.
        function labelText(el) {

            // First check whether the element has an associated label.
            if (el.labels && el.labels.length) {
                return Array.from(el.labels)
                    .map(x => x.innerText.trim())
                    .join(' ');
            }

            // Check aria-label.
            const aria = el.getAttribute('aria-label');
            if (aria) return aria;

            // Check aria-labelledby.
            const labelledBy = el.getAttribute('aria-labelledby');

            if (labelledBy) {
                return labelledBy
                    .split(' ')
                    .map(id => document.getElementById(id)?.innerText || '')
                    .join(' ')
                    .trim();
            }

            return '';
        }

        // STEP 4: Extract information from every visible element.
        return nodes
            .filter(visible)
            .map((el, index) => ({
                index,
                tag: el.tagName.toLowerCase(),
                type: el.getAttribute('type') || '',
                role: el.getAttribute('role') || '',

                text: (el.innerText || el.textContent || '')
                    .trim()
                    .slice(0, 160),

                label: labelText(el),

                placeholder: el.getAttribute('placeholder') || '',
                ariaLabel: el.getAttribute('aria-label') || '',
                name: el.getAttribute('name') || '',
                id: el.id || '',
                value: el.value || '',
                href: el.href || '',

                disabled: Boolean(el.disabled),
                required: Boolean(el.required),

                // Extract dropdown options if the element is SELECT.
                options: el.tagName === 'SELECT'
                    ? Array.from(el.options).map(o => ({
                        text: o.text.trim(),
                        value: o.value
                    }))
                    : [],

                // Store a limited HTML representation.
                outerHTML: el.outerHTML.slice(0, 500)
            }));
        """

        # STEP 5: Execute JavaScript and receive the extracted elements.
        elements = self.driver.execute_script(script)

        # Limit the number of returned elements.
        elements = elements[:max_elements]

        # Extract visible text from the webpage body.
        body_text = self.driver.find_element(
            By.TAG_NAME,
            "body",
        ).text

        # STEP 6: Build the final structured snapshot.
        return {
            "url": self.driver.current_url,
            "title": self.driver.title,
            "body_text": body_text[:6000],
            "elements": elements,
        }

    def print_snapshot(self, max_elements: int = 100) -> None:
        """
        PURPOSE:
            Display the webpage snapshot in readable JSON format.

        HOW IT WORKS:
            1. Calls get_page_snapshot().
            2. Receives the webpage information as a dictionary.
            3. Converts the dictionary into formatted JSON.
            4. Prints the JSON in the terminal.

        SAMPLE:
            browser.print_snapshot(max_elements=50)

        RESULT:
            Displays the webpage URL, title, body text
            and interactive elements in the terminal.

        WHY IMPORTANT:
            Useful for debugging and checking what the
            AI can observe on a webpage.
        """

        snapshot = self.get_page_snapshot(max_elements=max_elements)

        print(
            json.dumps(
                snapshot,
                indent=2,
                ensure_ascii=False,
            )
        )

    # ---------------------------------------------------------
    # BASIC INTERACTIONS
    # ---------------------------------------------------------

    def click(self, locator: tuple[str, str]) -> None:
        """
        PURPOSE:
            Click a button, link or another clickable element.

        HOW IT WORKS:
            1. Calls wait_for() with the clickable condition.
            2. Waits until the element becomes clickable.
            3. Uses Selenium's click() method.

        SAMPLE:
            browser.click((By.ID, "login-button"))

        RESULT:
            Selenium clicks the identified element.

        WHY IMPORTANT:
            Allows the AI test runner to perform
            actions such as clicking Login or Submit.
        """

        element = self.wait_for(
            locator,
            condition="clickable",
        )

        element.click()

    def fill(
        self,
        locator: tuple[str, str],
        value: str,
        clear_first: bool = True,
    ) -> None:
        """
        PURPOSE:
            Enter text into an input field or textarea.

        HOW IT WORKS:
            1. Finds the element using its locator.
            2. Waits until the element becomes visible.
            3. Clears existing text if clear_first is True.
            4. Uses send_keys() to enter the supplied value.

        SAMPLE:
            browser.fill(
                (By.ID, "email"),
                "test@example.com"
            )

        RESULT:
            The email input receives the supplied text.

        WHY IMPORTANT:
            Allows automated testing of forms,
            search fields and text inputs.
        """

        element = self.wait_for(
            locator,
            condition="visible",
        )

        # Remove previously entered text when requested.
        if clear_first:
            element.clear()

        # Enter the new text.
        element.send_keys(value)

    def select_option(
        self,
        locator: tuple[str, str],
        value: str | None = None,
        text: str | None = None,
    ) -> None:
        """
        PURPOSE:
            Select an option from a native HTML dropdown.

        HOW IT WORKS:
            1. Imports Selenium's Select class.
            2. Locates the dropdown element.
            3. Creates a Select object.
            4. Selects an option using either its value or text.
            5. Raises an error if neither is provided.

        SAMPLE 1: Select using value.

            browser.select_option(
                (By.ID, "country"),
                value="IN"
            )

        SAMPLE 2: Select using visible text.

            browser.select_option(
                (By.ID, "country"),
                text="India"
            )

        RESULT:
            The requested dropdown option becomes selected.

        IMPORTANT:
            This method supports native HTML SELECT elements.
            Custom JavaScript dropdowns need a different approach.
        """

        from selenium.webdriver.support.ui import Select

        element = self.wait_for(
            locator,
            condition="visible",
        )

        select = Select(element)

        # Select using the HTML option value attribute.
        if value is not None:
            select.select_by_value(value)

        # Select using the visible option text.
        elif text is not None:
            select.select_by_visible_text(text)

        else:
            raise ValueError("Provide value or text.")

    # ---------------------------------------------------------
    # SCREENSHOTS
    # ---------------------------------------------------------

    def screenshot(self, filename: str = "page.png") -> str:
        """
        PURPOSE:
            Capture a screenshot of the current webpage.

        HOW IT WORKS:
            1. Checks whether Chrome is running.
            2. Creates a screenshot path using screenshot_dir.
            3. Uses Selenium's save_screenshot().
            4. Converts the saved path into an absolute path.
            5. Returns that path.

        SAMPLE:
            path = browser.screenshot("login_page.png")
            print(path)

        RESULT:
            Saves an image of the current browser window.

            Example:
                screenshots/login_page.png

        WHY IMPORTANT:
            Screenshots can help developers inspect test results
            and diagnose visual issues.
        """

        self._require_driver()

        # Construct the screenshot file path.
        path = self.screenshot_dir / filename

        # Capture the current browser window.
        self.driver.save_screenshot(str(path))

        # Return the complete absolute file path.
        return str(path.resolve())

    # ---------------------------------------------------------
    # INTERNAL UTILITIES
    # ---------------------------------------------------------

    def _require_driver(self) -> None:
        """
        PURPOSE:
            Check whether a Chrome browser session is active.

        HOW IT WORKS:
            1. Checks the self.driver variable.
            2. If it is None, Chrome has not been started
               or the session has already been closed.
            3. Raises RuntimeError to prevent further execution.

        SAMPLE:
            browser = BrowserEngine()
            browser.current_url()

        RESULT:
            Raises:
                RuntimeError:
                Browser is not running. Call start() first.

        WHY IMPORTANT:
            Prevents browser functions from executing
            without an active Selenium WebDriver session.
        """

        if self.driver is None:
            raise RuntimeError(
                "Browser is not running. Call start() first."
            )
