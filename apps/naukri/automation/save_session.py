"""Save Naukri login session (visible browser)."""

import os
import time

from playwright.sync_api import sync_playwright

from naukri_config import STORAGE_STATE_PATH


def main():
    print("Opening Naukri login — sign in manually, then close when done.")
    print("Session will be saved for headless apply runs.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1366, "height": 900})
        page = context.new_page()
        page.goto("https://www.naukri.com/nlogin/login", wait_until="domcontentloaded")
        print("Waiting for login... (detecting mnuser / dashboard URL)")

        deadline = time.time() + 300
        while time.time() < deadline:
            url = (page.url or "").lower()
            if any(token in url for token in ("mnjuser", "myapply", "recommendedjobs", "homepage")):
                if "login" not in url:
                    break
            page.wait_for_timeout(1500)

        os.makedirs(os.path.dirname(STORAGE_STATE_PATH), exist_ok=True)
        context.storage_state(path=STORAGE_STATE_PATH)
        print(f"Session saved: {STORAGE_STATE_PATH}")
        browser.close()


if __name__ == "__main__":
    main()
