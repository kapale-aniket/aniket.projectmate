from common.bootstrap import ensure_automation_path

ensure_automation_path()

import subprocess
import sys

from playwright.sync_api import sync_playwright

from common.browser import STORAGE_STATE_PATH


def ensure_chromium_installed():
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
    except Exception:
        print("Installing Chromium...")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
        )


def main():
    ensure_chromium_installed()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.linkedin.com/login")

        print("Log in manually in the browser window.")

        login_timeout_seconds = 300
        poll_seconds = 2
        logged_in = False
        for _ in range(login_timeout_seconds // poll_seconds):
            cookies = context.cookies("https://www.linkedin.com")
            if any(c["name"] == "li_at" and c.get("value") for c in cookies):
                logged_in = True
                break
            page.wait_for_timeout(poll_seconds * 1000)

        if not logged_in:
            print("Login timed out. Session not saved.")
            browser.close()
            raise SystemExit(1)

        context.storage_state(path=STORAGE_STATE_PATH)
        print(f"Session saved: {STORAGE_STATE_PATH}")
        browser.close()


if __name__ == "__main__":
    main()
