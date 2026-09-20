import os
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_STATE_PATH = os.path.join(_MODULE_DIR, "storage_state.json")

DEFAULT_BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}

TRACKER_URL_MARKERS = (
    "google-analytics.com",
    "googletagmanager.com",
    "doubleclick.net",
    "adservice.google.com",
    "px.ads.linkedin.com",
    "ads.linkedin.com",
    "bat.bing.com",
    "connect.facebook.net",
    "facebook.com/tr",
    "scorecardresearch.com",
    "demdex.net",
)


def _make_route_handler(blocked_types, block_trackers):
    def handler(route):
        try:
            request = route.request
            url = request.url.lower()
            if request.resource_type in blocked_types or (
                block_trackers and any(marker in url for marker in TRACKER_URL_MARKERS)
            ):
                route.abort()
            else:
                route.continue_()
        except Exception:
            try:
                route.continue_()
            except Exception:
                pass

    return handler


@contextmanager
def launch_browser(
    headless=False,
    blocked_resource_types=None,
    block_trackers=True,
    storage_state=STORAGE_STATE_PATH,
):
    if blocked_resource_types is None:
        blocked_resource_types = DEFAULT_BLOCKED_RESOURCE_TYPES
    blocked_types = set(blocked_resource_types)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        # Playwright accepts either a path to a storage file or a dict. If the
        # provided path does not exist, pass an empty dict so Playwright won't
        # attempt to open a missing file and raise FileNotFoundError.
        storage_arg = storage_state
        try:
            if isinstance(storage_state, str) and not os.path.exists(storage_state):
                storage_arg = {}
        except Exception:
            storage_arg = {}
        context = browser.new_context(storage_state=storage_arg)
        if blocked_types or block_trackers:
            context.route("**/*", _make_route_handler(blocked_types, block_trackers))
        page = context.new_page()
        try:
            yield browser, context, page
        finally:
            browser.close()
