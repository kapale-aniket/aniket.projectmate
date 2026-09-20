"""Naukri apply flow: today's email applications → Python recommended jobs → multi-apply."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from browser import launch_browser
from naukri_config import JOB_KEYWORD, MULTI_APPLY_BATCH_SIZE, STORAGE_STATE_PATH
from helpers import ensure_logged_in, pause
from history import scrape_today_email_applications
from apply_flow import scrape_and_apply_python_jobs


def run(config=None):
    config = config or {}
    keyword = (config.get("job_keyword") or JOB_KEYWORD or "python").strip()
    batch_size = int(config.get("multi_apply_batch_size") or MULTI_APPLY_BATCH_SIZE or 5)
    # Default visible browser so user can watch / Show opens the Naukri window
    headless = bool(config.get("headless", False))

    import naukri_config as cfg

    cfg.JOB_KEYWORD = keyword
    cfg.MULTI_APPLY_BATCH_SIZE = batch_size

    print("Starting Naukri apply flow...")
    print(f"  Keyword filter : {keyword}")
    print(f"  Multi-apply    : {batch_size} jobs at a time")
    print(f"  Browser        : {'headless' if headless else 'visible window'}")
    print(f"  Session file   : {STORAGE_STATE_PATH}")

    if not os.path.exists(STORAGE_STATE_PATH):
        print("*** Naukri session missing. Open Session tab and save login first. ***")
        raise SystemExit(1)

    task_id = os.environ.get("TERRA_TASK_ID") or os.environ.get("NAUKRI_TASK_ID")

    with launch_browser(headless=headless) as (browser, context, page):
        if task_id:
            try:
                from apps.linkedin.services.browser_preview import register_page, unregister_page

                register_page(page, int(task_id))
            except Exception:
                unregister_page = None
        else:
            unregister_page = None

        try:
            page.goto(
                "https://www.naukri.com/mnjuser/homepage",
                wait_until="domcontentloaded",
                timeout=90000,
            )
            pause(page, 1, 2)
            if not ensure_logged_in(page):
                print("*** Naukri session expired. Re-save session from Session tab. ***")
                raise SystemExit(1)

            print("\n[1/2] Scraping today's Connected-by-Email applications...")
            history_rows = scrape_today_email_applications(page, logger=print)

            print("\n[2/2] Scraping Python recommended jobs and multi-applying...")
            jobs, applied = scrape_and_apply_python_jobs(
                page, logger=print, batch_size=batch_size
            )

            print("\nDone.")
            print(f"  Email applications today : {len(history_rows)}")
            print(f"  Python recommended jobs  : {len(jobs)}")
            print(f"  Multi-apply attempted    : {len(applied)}")
        finally:
            if unregister_page:
                try:
                    unregister_page()
                except Exception:
                    pass


if __name__ == "__main__":
    run()
