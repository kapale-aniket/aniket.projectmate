from common.bootstrap import ensure_automation_path

ensure_automation_path()

import os
import re
import signal
import sys
import threading
import time
from datetime import date
from urllib.parse import quote

from common.browser import launch_browser
from common.helpers import search_delay
from common.job_age import job_age_label, linkedin_time_filter_param
from common.senior_filter import is_senior_text
from common.session import check_session_on_job_search
from job.config import (
    JOB_KEYWORDS,
    LOCATIONS,
    MAX_JOB_AGE_HOURS,
    MAX_JOBS,
    MAX_PAGES,
    RESULTS_PER_PAGE,
    SEARCH_MAX_DELAY,
    SEARCH_MIN_DELAY,
)
from job.job_scraper import parse_job_detail
from job.job_filter import (
    deduplicate_jobs,
    job_id_from_url,
    normalize_job,
    parse_posted,
    should_skip_for_fresher_filter,
    sort_jobs_newest_first,
)
from job.excel_writer import write_branded_excel
from job.master_store import (
    OUTPUT_DIR,
    count_previous_daily_files,
    daily_excel_path,
    ensure_daily_excel,
    job_ids_from_jobs,
    known_job_ids,
    load_today_store,
    save_today_store,
    summarize_known_jobs,
)
from job.scrape_state import (
    checkpoint_context,
    clear_checkpoint,
    default_checkpoint,
    load_checkpoint,
    save_checkpoint,
    sync_checkpoint_context,
)

os.makedirs(OUTPUT_DIR, exist_ok=True)

stop_requested = False
interrupt_pending = False
jobs_collected = 0
progress = default_checkpoint()
_active_save_ctx = None
_stop_watcher_stop = threading.Event()


def pause_search(page):
    search_delay(page, SEARCH_MIN_DELAY, SEARCH_MAX_DELAY)

CARD_POSTED_PATTERN = re.compile(
    r"(?:just now|\d+\s*(?:second|minute|hour|day|week|month|year)s?\s+ago)",
    re.IGNORECASE,
)
NETWORK_ERROR_MARKERS = (
    "net::err",
    "err_internet_disconnected",
    "err_name_not_resolved",
    "err_network_changed",
    "err_connection",
    "err_proxy",
    "err_timed_out",
    "name_not_resolved",
    "connection refused",
    "connection reset",
    "target page, context or browser has been closed",
)


def handle_interrupt_signal(signum, frame):
    global interrupt_pending, stop_requested
    if is_noninteractive():
        stop_requested = True
        interrupt_pending = False
        progress["interrupted"] = True
        sync_checkpoint_context(progress)
        save_checkpoint(progress)
        flush_active_save(force_excel=True)
        print("\n*** Stop signal received — saving and exiting. ***")
        return
    if stop_requested:
        raise KeyboardInterrupt
    if not interrupt_pending:
        interrupt_pending = True
        label = "Ctrl+C" if signum == signal.SIGINT else "terminal closing"
        print(f"\n*** Interrupt detected ({label}). ***")


def register_interrupt_handlers():
    signal.signal(signal.SIGINT, handle_interrupt_signal)
    for sig_name in ("SIGTERM", "SIGHUP"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, handle_interrupt_signal)
        except (ValueError, OSError):
            pass


register_interrupt_handlers()


def is_noninteractive():
    return os.environ.get("TERRA_NONINTERACTIVE") == "1" or not sys.stdin.isatty()


def prompt_stop_or_resume(context_msg, mark_stopped=True):
    global stop_requested, interrupt_pending
    if is_noninteractive():
        interrupt_pending = False
        print(f"[Auto-resume] Continuing after: {context_msg}")
        return True

    print("\n" + "=" * 64)
    print("*** SCRAPING PAUSED ***")
    print(f"    {context_msg}")
    print("    1 = STOP scraping and SAVE file")
    print("    2 = RESUME from where you stopped")
    print("=" * 64)
    while True:
        try:
            choice = input("Your choice [1/2]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nTerminal closed — saving and stopping.")
            choice = "1"
        if choice == "1":
            if mark_stopped:
                stop_requested = True
            interrupt_pending = False
            progress["interrupted"] = True
            sync_checkpoint_context(progress)
            save_checkpoint(progress)
            return False
        if choice == "2":
            interrupt_pending = False
            print("Resuming scrape...")
            return True
        print("    Type 1 or 2.")


def persist_progress(context_msg):
    progress["interrupted"] = True
    sync_checkpoint_context(progress)
    save_checkpoint(progress)
    return prompt_stop_or_resume(context_msg)


def _django_stop_requested():
    global stop_requested
    task_id = os.environ.get("TERRA_TASK_ID")
    data_dir = os.environ.get("TERRA_DATA_DIR")
    if not task_id or not data_dir:
        return False
    flag = os.path.join(data_dir, f"stop_task_{task_id}")
    if os.path.isfile(flag):
        stop_requested = True
        progress["interrupted"] = True
        sync_checkpoint_context(progress)
        save_checkpoint(progress)
        try:
            os.remove(flag)
        except OSError:
            pass
        flush_active_save(force_excel=True)
        print("\n*** Stop requested from dashboard — saving and exiting. ***")
        return True
    return False


def _register_save_context(pending_jobs, today_store):
    global _active_save_ctx
    _active_save_ctx = {"pending": pending_jobs, "store": today_store}


def flush_active_save(force_excel=False):
    ctx = _active_save_ctx
    if not ctx:
        return
    pending = ctx.get("pending") or []
    store = ctx.get("store")
    if not store:
        return
    if pending:
        batch = list(pending)
        pending.clear()
        save_progress(batch, store)
    elif force_excel:
        save_progress([], store)
        if not store.get("jobs"):
            from job.master_store import ensure_daily_excel

            ensure_daily_excel(store)


def _stop_watcher_loop():
    while not _stop_watcher_stop.wait(0.5):
        if _django_stop_requested():
            break


def _start_stop_watcher():
    _stop_watcher_stop.clear()
    thread = threading.Thread(target=_stop_watcher_loop, daemon=True, name="job-stop-watcher")
    thread.start()
    return thread


def _stop_stop_watcher():
    _stop_watcher_stop.set()


def check_interrupt(page, context_msg):
    _django_stop_requested()
    if stop_requested:
        return False
    if interrupt_pending:
        return persist_progress(context_msg)
    if page and is_offline(page):
        return persist_progress(f"No internet — {context_msg}")
    return True


def has_title_and_company(job):
    return bool(job.get("job_title") and job.get("company_name"))


def is_senior_title(text):
    return is_senior_text(text)


def is_stale_job_card(card_text, max_hours=None):
    if max_hours is None:
        max_hours = MAX_JOB_AGE_HOURS
    match = CARD_POSTED_PATTERN.search(card_text or "")
    if not match:
        return False
    hours, _ = parse_posted(match.group(0), max_hours=max_hours)
    return hours is None


def page_has_no_jobs(page):
    try:
        body = page.locator("body").inner_text().lower()
    except Exception:
        return False
    return (
        "no matching jobs found" in body
        or "no results found" in body
        or "unfortunately, we couldn't find" in body
        or "we couldn't find a match" in body
    )


def wait_for_job_results(page, max_attempts=6):
    """Wait for cards to load before treating a search as empty."""
    for attempt in range(max_attempts):
        if not check_interrupt(page, "while waiting for job results"):
            return "interrupted"
        cards = locate_job_cards(page)
        if cards.count() > 0:
            return "ready"
        if attempt >= 2 and page_has_no_jobs(page):
            return "empty"
        page.mouse.wheel(0, 2500)
        pause_search(page)
    cards = locate_job_cards(page)
    if cards.count() > 0:
        return "ready"
    if page_has_no_jobs(page):
        return "empty"
    return "unknown"


def is_network_error(exc):
    msg = str(exc).lower()
    return any(marker in msg for marker in NETWORK_ERROR_MARKERS)


def is_offline(page):
    try:
        return page.evaluate("navigator.onLine") is False
    except Exception:
        return False


def wait_until_online(page, max_seconds=180):
    waited = 0
    while waited < max_seconds:
        if stop_requested:
            return
        try:
            if page.evaluate("navigator.onLine"):
                print("  Connection restored. Retrying...")
                return
        except Exception:
            pass
        page.wait_for_timeout(2000)
        waited += 2
        if waited % 10 == 0:
            print(f"  ...still waiting for internet ({waited}s)")


def open_page_with_retry(page, url, context_msg):
    while True:
        if stop_requested:
            return False
        if not check_interrupt(page, context_msg):
            return False
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
            return True
        except Exception as exc:
            if is_offline(page) or is_network_error(exc):
                if persist_progress(f"No internet — {context_msg}"):
                    wait_until_online(page)
                    continue
                return False
            print(f"  Load error: {exc}")
            return False


def read_job_id_from_card(card):
    for attr in ("data-job-id", "data-occludable-job-id"):
        try:
            value = card.get_attribute(attr)
        except Exception:
            value = None
        if value and value.isdigit():
            return value
    try:
        href = card.locator("a[href*='/jobs/view/']").first.get_attribute("href")
    except Exception:
        href = None
    return job_id_from_url(href)


def locate_job_cards(page):
    """Find job result cards using LinkedIn's current or legacy selectors."""
    for selector in (
        ".job-card-container",
        "li.jobs-search-results__list-item",
        "div.job-card-list__entity-lockup",
        "[data-occludable-job-id]",
    ):
        cards = page.locator(selector)
        if cards.count() > 0:
            return cards
    return page.locator(".job-card-container")


def mark_job_noticed(job_id, saved_job_ids):
    if job_id:
        saved_job_ids.add(job_id)


def scrape_job_card(page, cards, index, seen_apply_urls, saved_job_ids):
    card = cards.nth(index)
    card_job_id = read_job_id_from_card(card)
    if card_job_id and card_job_id in saved_job_ids:
        print(f"  Already noticed job {card_job_id} (card {index + 1}) — skipping.")
        return None

    try:
        card_text = card.inner_text()
    except Exception:
        card_text = ""

    if is_senior_title(card_text):
        print(f"  Skipping senior-level role (card {index + 1}).")
        mark_job_noticed(card_job_id, saved_job_ids)
        return None
    if is_stale_job_card(card_text, MAX_JOB_AGE_HOURS):
        print(
            f"  Skipping job older than {MAX_JOB_AGE_HOURS}h (card {index + 1})."
        )
        mark_job_noticed(card_job_id, saved_job_ids)
        return None

    pause_search(page)
    card.click()
    pause_search(page)

    try:
        page.wait_for_selector("text=About the job", timeout=8000)
    except Exception:
        if is_offline(page):
            raise
        return None

    pause_search(page)
    apply_link = page.url
    opened_job_id = job_id_from_url(apply_link) or card_job_id
    if opened_job_id and opened_job_id in saved_job_ids:
        return None
    if apply_link in seen_apply_urls:
        mark_job_noticed(opened_job_id, saved_job_ids)
        return None

    seen_apply_urls.add(apply_link)
    page_text = page.locator("body").inner_text()
    raw_job = parse_job_detail(page_text, apply_link=apply_link)
    if not has_title_and_company(raw_job):
        mark_job_noticed(opened_job_id, saved_job_ids)
        return None
    if is_senior_title(raw_job.get("job_title", "")):
        print(f"  Skipping senior-level role: {raw_job.get('job_title', '')[:60]}")
        mark_job_noticed(opened_job_id, saved_job_ids)
        return None

    skip, skip_reason = should_skip_for_fresher_filter(
        description_text=raw_job.get("description_text", ""),
        job_title=raw_job.get("job_title", ""),
        experience_raw=raw_job.get("experience_raw", ""),
    )
    if skip:
        print(f"  Skipping ({skip_reason}): {raw_job.get('job_title', '')[:60]}")
        mark_job_noticed(opened_job_id, saved_job_ids)
        return None

    job = normalize_job(raw_job)
    mark_job_noticed(
        job_id_from_url(job["apply_link"]) if job else opened_job_id,
        saved_job_ids,
    )
    return job


def scrape_results_page(page, seen_apply_urls, saved_job_ids, start_card=0):
    global stop_requested, jobs_collected, progress

    pause_search(page)
    for _ in range(8):
        if not check_interrupt(page, "while loading job cards"):
            return [], 0, 0, False
        page.mouse.wheel(0, 4000)
        pause_search(page)

    cards = locate_job_cards(page)
    card_count = cards.count()
    known_on_page = sum(
        1
        for idx in range(card_count)
        if (read_job_id_from_card(cards.nth(idx)) or "") in saved_job_ids
    )
    print(
        f"  Cards on this page: {card_count} "
        f"({known_on_page} already noticed, {card_count - known_on_page} to check)"
    )

    page_jobs = []
    stale_age_on_page = 0
    index = start_card
    while index < card_count:
        progress["card_index"] = index
        sync_checkpoint_context(progress)
        save_checkpoint(progress)

        if not check_interrupt(
            page,
            f"while reading job {index + 1} of {card_count} on this page",
        ):
            break

        card = cards.nth(index)
        card_job_id = read_job_id_from_card(card)
        if card_job_id and card_job_id in saved_job_ids:
            index += 1
            continue

        try:
            card_text = card.inner_text()
        except Exception:
            card_text = ""

        if is_stale_job_card(card_text, MAX_JOB_AGE_HOURS):
            stale_age_on_page += 1
            print(
                f"  Skipping job older than {MAX_JOB_AGE_HOURS}h (card {index + 1})."
            )
            mark_job_noticed(card_job_id, saved_job_ids)
            index += 1
            continue

        try:
            job = scrape_job_card(page, cards, index, seen_apply_urls, saved_job_ids)
        except Exception as exc:
            if is_offline(page) or is_network_error(exc):
                if persist_progress(
                    f"No internet — job {index + 1} of {card_count} on this page"
                ):
                    wait_until_online(page)
                    continue
                break
            print(f"  ERROR on card {index}: {exc}")
            index += 1
            continue

        if job is not None:
            page_jobs.append(job)
            jobs_collected += 1
            print(
                f"  {job['job_role']} | {job['company_name']} | "
                f"{job['posted_text']} | {job['freshers_eligible']}"
            )
            if MAX_JOBS and jobs_collected >= MAX_JOBS:
                print(f"  Reached MAX_JOBS={MAX_JOBS}. Stopping scrape.")
                stop_requested = True
                break

        pause_search(page)
        index += 1

    progress["card_index"] = 0
    all_stale_age = card_count > 0 and stale_age_on_page > 0 and stale_age_on_page + known_on_page >= card_count
    if all_stale_age:
        print(
            f"  All visible cards are older than {MAX_JOB_AGE_HOURS}h — stopping this search."
        )
    return page_jobs, card_count, known_on_page, all_stale_age


def scrape_keyword_search(page, keyword, location, saved_job_ids, start_page=0, on_batch_saved=None):
    print(f"\nSearching: {keyword} | {location} ({job_age_label(MAX_JOB_AGE_HOURS)})")
    scraped_jobs = []
    seen_apply_urls = set()
    time_filter = linkedin_time_filter_param(MAX_JOB_AGE_HOURS)

    for page_num in range(start_page, MAX_PAGES):
        progress["page_num"] = page_num
        sync_checkpoint_context(progress)
        save_checkpoint(progress)

        if not check_interrupt(page, f"before page {page_num + 1} of {keyword} | {location}"):
            print("  Stop requested. Halting pagination.")
            break

        start = page_num * RESULTS_PER_PAGE
        search_url = (
            "https://www.linkedin.com/jobs/search/"
            f"?keywords={quote(keyword)}"
            f"&location={quote(location)}"
            f"&f_TPR={time_filter}"
            f"&sortBy=DD"
            f"&start={start}"
        )
        print(f"  Page {page_num + 1} (start={start})")

        if not open_page_with_retry(page, search_url, f"loading page {page_num + 1}"):
            if stop_requested:
                print("  Stop requested. Halting pagination.")
            else:
                print("  SKIP (page load failed).")
            break

        pause_search(page)
        load_state = wait_for_job_results(page)
        if load_state == "interrupted":
            print("  Stop requested. Halting pagination.")
            break
        if load_state == "empty":
            print("  No matching jobs for this keyword/location.")
            break
        if load_state == "unknown":
            print("  Job cards did not load on this page — moving on.")
            break

        start_card = progress.get("card_index", 0) if page_num == start_page else 0
        page_jobs, card_count, known_on_page, all_stale_age = scrape_results_page(
            page,
            seen_apply_urls,
            saved_job_ids,
            start_card=start_card,
        )
        scraped_jobs.extend(page_jobs)

        if all_stale_age:
            print("  Job age filter reached — no newer listings on this search.")
            break

        if card_count == 0:
            print("  No cards on this page. Stopping pagination for this search.")
            break
        if page_jobs:
            print(f"  Found {len(page_jobs)} new job(s) on page {page_num + 1}.")
            if on_batch_saved:
                on_batch_saved(page_jobs)
        elif known_on_page == card_count:
            print(
                f"  Page {page_num + 1}: all {known_on_page} card(s) already noticed — "
                "continuing to next page."
            )
        else:
            print(
                f"  Page {page_num + 1}: no new jobs ({card_count} card(s) checked) — "
                "continuing to next page."
            )

        pause_search(page)

    progress["page_num"] = 0
    progress["card_index"] = 0
    print(f"  Total jobs collected: {len(scraped_jobs)} across pages")
    return scraped_jobs


def is_logged_in(page):
    return check_session_on_job_search(page)


def save_progress(jobs_this_run, today_store):
    new_jobs = sort_jobs_newest_first(deduplicate_jobs(jobs_this_run))
    all_today_jobs = deduplicate_jobs(new_jobs + today_store["jobs"])
    today_store["jobs"] = all_today_jobs
    save_today_store(today_store)

    excel_path = daily_excel_path()
    try:
        row_count = write_branded_excel(all_today_jobs, excel_path)
        print(
            f"\nDaily Excel: {excel_path} - {len(new_jobs)} new this run, "
            f"{len(all_today_jobs)} total today ({row_count} shown after filters)."
        )
    except Exception as exc:
        from common.file_errors import friendly_file_error

        if isinstance(exc, OSError):
            detail = friendly_file_error(exc, excel_path, "write")
        else:
            detail = f"Could not write Excel ({exc})"
        print(f"\n*** {detail} ***")
        print("  Today's JSON backup was saved. Close the Excel file and run again to refresh it.")
    return len(new_jobs), len(all_today_jobs)


def resolve_start_progress():
    global progress
    today = date.today().strftime("%Y-%m-%d")
    checkpoint = load_checkpoint()

    if checkpoint.get("interrupted") and checkpoint.get("date") == today:
        context = checkpoint.get("context") or checkpoint_context(checkpoint)
        print(f"\nPrevious scrape was interrupted at: {context}")
        if prompt_stop_or_resume("Resume previous scrape?", mark_stopped=False):
            progress = checkpoint
            print(f"Resuming from: {checkpoint_context(progress)}")
            return "resume"
        print("Starting a fresh scrape (previous checkpoint cleared).")
        clear_checkpoint()
        progress = default_checkpoint()
        return "fresh"

    if checkpoint.get("date") != today:
        clear_checkpoint()
    progress = default_checkpoint()
    return "fresh"


def run():
    global stop_requested, progress
    start_mode = resolve_start_progress()
    if start_mode == "exit":
        return
    resuming = start_mode == "resume"

    with launch_browser(blocked_resource_types={"image", "media", "font"}) as (
        browser,
        context,
        page,
    ):
        page.goto(
            "https://www.linkedin.com/jobs/",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        pause_search(page)

        if not is_logged_in(page):
            print("\n*** LinkedIn session expired! ***")
            print("Run: python common/save_session.py")
            print("Then: python job/job.py")
            raise SystemExit(1)

        today_store = load_today_store()
        saved_job_ids = known_job_ids()
        previous_day_count = count_previous_daily_files()
        already_saved_today = len(job_ids_from_jobs(today_store["jobs"]))
        excel_path = ensure_daily_excel(today_store)
        print(f"Daily output: {excel_path} ({previous_day_count} previous day file(s)).")
        previous_summary = summarize_known_jobs()
        if previous_summary:
            print("Previous daily files:")
            for day_label, job_count in previous_summary:
                print(f"  - {day_label}: {job_count} job(s)")
        print(
            f"Already noticed {len(saved_job_ids)} job(s) "
            f"({already_saved_today} from earlier today, rest from previous days)."
        )
        print("Scraping searches one by one; only new jobs are added to today's Excel.")
        if resuming:
            print(f"Resume point: {checkpoint_context(progress)}")

        jobs_this_run = []
        pending_jobs = jobs_this_run
        _register_save_context(pending_jobs, today_store)
        _start_stop_watcher()
        keyword_start = progress.get("keyword_index", 0)
        location_start = progress.get("location_index", 0)
        page_start = progress.get("page_num", 0)

        def persist_job_batch(batch):
            if not batch:
                return
            pending_jobs.extend(batch)
            save_progress(pending_jobs, today_store)
            pending_jobs.clear()

        try:
            for keyword_index, keyword in enumerate(JOB_KEYWORDS):
                if keyword_index < keyword_start:
                    continue
                progress["keyword_index"] = keyword_index
                sync_checkpoint_context(progress)
                save_checkpoint(progress)

                if not check_interrupt(page, f"before keyword {keyword}"):
                    break

                location_from = location_start if keyword_index == keyword_start else 0
                for location_index, location in enumerate(LOCATIONS):
                    if location_index < location_from:
                        continue
                    progress["location_index"] = location_index
                    sync_checkpoint_context(progress)
                    save_checkpoint(progress)

                    if not check_interrupt(page, f"before location {location}"):
                        break
                    try:
                        pause_search(page)
                        start_page = page_start if (
                            keyword_index == keyword_start
                            and location_index == location_start
                        ) else 0
                        scraped_jobs = scrape_keyword_search(
                            page,
                            keyword,
                            location,
                            saved_job_ids,
                            start_page=start_page,
                            on_batch_saved=persist_job_batch,
                        )
                        page_start = 0
                        print(
                            f"Finished {keyword_index + 1}/{len(JOB_KEYWORDS)} keywords, "
                            f"{location_index + 1}/{len(LOCATIONS)} locations: "
                            f"{keyword} | {location} "
                            f"({len(scraped_jobs)} new job(s) this search)"
                        )
                        if stop_requested:
                            break
                    except Exception as exc:
                        if is_network_error(exc):
                            if persist_progress(f"Network error during {keyword} | {location}"):
                                wait_until_online(page)
                                continue
                            break
                        print(f"  Keyword failed ({keyword}): {exc}")

                location_start = 0
                if stop_requested:
                    break
        finally:
            _stop_stop_watcher()
            flush_active_save(force_excel=True)
            if stop_requested or progress.get("interrupted"):
                progress["interrupted"] = True
                sync_checkpoint_context(progress)
                save_checkpoint(progress)
            else:
                clear_checkpoint()

    if stop_requested:
        file_name = os.path.basename(daily_excel_path())
        print(
            f"\nStopped — progress saved. Check \"{file_name}\" in Output."
        )
    else:
        file_name = os.path.basename(daily_excel_path())
        print(f'\nScraping completed. Check "{file_name}" in Output.')


if __name__ == "__main__":
    run()
