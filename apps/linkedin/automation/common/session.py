"""LinkedIn session checks shared by job, connection, and posts scrapers."""

from common.helpers import search_delay

FEED_URL = "https://www.linkedin.com/feed/"
SESSION_URL_MARKERS = ("login", "authwall", "/uas/")
SESSION_EXPIRED_MSG = "LinkedIn session expired. Run: python common/save_session.py"


def check_session_via_feed(page, min_delay=1.0, max_delay=2.0, logger=None):
    page.goto(FEED_URL, wait_until="domcontentloaded", timeout=60000)
    search_delay(page, min_delay, max_delay)
    if any(marker in page.url for marker in SESSION_URL_MARKERS):
        if logger:
            logger.info(SESSION_EXPIRED_MSG)
        return False
    return True


def check_session_on_job_search(page):
    body = page.locator("body").inner_text().lower()
    if "sign in to create job alert" in body or "join now" in body[:500]:
        return False
    return True
