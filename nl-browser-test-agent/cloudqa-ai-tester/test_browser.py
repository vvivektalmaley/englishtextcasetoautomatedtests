
# test_browser.py

from browser_engine import BrowserEngine


def main():
    browser = BrowserEngine(headless=False)

    try:
        browser.start()

        print("Opening website...")
        browser.open("https://example.com")

        print("\nBrowser started successfully!")
        print("Title:", browser.page_title())
        print("URL:", browser.current_url())

        print("\nDOM snapshot:")
        browser.print_snapshot()

        screenshot_path = browser.screenshot(
            "browser_test.png"
        )

        print("\nScreenshot saved:", screenshot_path)

        input("\nPress Enter to close the browser...")

    finally:
        browser.close()


if __name__ == "__main__":
    main()
