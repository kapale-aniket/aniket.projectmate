import random
import time


def search_delay(page=None, min_seconds=1.0, max_seconds=2.0):
    if page is not None:
        try:
            from apps.linkedin.services.browser_preview import maybe_capture_screenshot

            maybe_capture_screenshot(page)
        except Exception:
            pass
    seconds = random.uniform(min_seconds, max_seconds)
    if page is not None:
        page.wait_for_timeout(int(seconds * 1000))
    else:
        time.sleep(seconds)


def invite_delay(page, min_seconds=8, max_seconds=15):
    search_delay(page, min_seconds, max_seconds)
