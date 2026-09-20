import os
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

from naukri_config import STORAGE_STATE_PATH


@contextmanager
def launch_browser(headless=False, storage_state=None):
    state = storage_state if storage_state is not None else STORAGE_STATE_PATH
    storage_arg = state
    if isinstance(state, str) and not os.path.exists(state):
        storage_arg = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(
            storage_state=storage_arg,
            viewport={"width": 1366, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        try:
            yield browser, context, page
        finally:
            try:
                context.storage_state(path=STORAGE_STATE_PATH)
            except Exception:
                pass
            browser.close()
