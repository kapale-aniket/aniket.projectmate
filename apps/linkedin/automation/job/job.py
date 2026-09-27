from common.bootstrap import ensure_automation_path

ensure_automation_path()

import os
import json
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
from common.search_skip import is_search_skipped, load_runtime_skip_searches
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
try:
    from job.config import (
        SKIP_SEARCHES,
        SKIP_PREVIOUS_JOBS,
        JOB_SEARCH_DISTANCE_KM,
        JOB_SEARCH_SORT_BY,
        SCRAPE_MODE,
        PERFECT_MATCH_SKILLS,
        PERFECT_MATCH_EXPERIENCE,
        PERFECT_MATCH_MIN_SKILLS,
    )
except ImportError:
    SKIP_SEARCHES = []
    SKIP_PREVIOUS_JOBS = False
    JOB_SEARCH_SORT_BY = "R"
    JOB_SEARCH_DISTANCE_KM = 100
    SCRAPE_MODE = "job"
    PERFECT_MATCH_SKILLS = []
    PERFECT_MATCH_EXPERIENCE = ""
    PERFECT_MATCH_MIN_SKILLS = 1
from job.job_scraper import parse_job_detail
from job.job_filter import (
    KEYWORD_MATCH_MODE,
    deduplicate_jobs,
    job_id_from_url,
    keyword_match_terms,
    normalize_job,
    parse_posted,
    should_skip_for_fresher_filter,
    should_skip_for_keyword_mismatch,
    should_skip_for_perfect_match,
    sort_jobs_newest_first,
)
from job.excel_writer import write_branded_excel
from job.geo_ids import resolve_job_geo_id
from job.master_store import (
    OUTPUT_DIR,
    count_previous_daily_files,
    daily_excel_path,
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
    normalize_resume_indices,
    save_checkpoint,
    search_plan_signature,
    sync_checkpoint_context,
)

os.makedirs(OUTPUT_DIR, exist_ok=True)
try:
    # Permanently delete job output older than 2 days on startup
    from job.master_store import purge_old_files

    purge_old_files()
except Exception:
    pass

stop_requested = False
interrupt_pending = False
jobs_collected = 0
progress = default_checkpoint()
_active_save_ctx = None
_stop_watcher_stop = threading.Event()
_battery_watcher_stop = threading.Event()
_low_battery_triggered = False


def current_skip_searches():
    runtime = load_runtime_skip_searches()
    if runtime is not None:
        return runtime
    return SKIP_SEARCHES


def pause_search(page):
    _check_low_battery_guard()
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
        save_progress(batch, store, write_excel=force_excel)
    elif force_excel:
        save_progress([], store, write_excel=True)


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


def _check_low_battery_guard():
    """If battery below configured % and unplugged: save Excel, stop scrape, shut down."""
    global stop_requested, interrupt_pending, _low_battery_triggered
    if _low_battery_triggered or stop_requested:
        return True
    try:
        from common.battery_guard import (
            format_status,
            get_battery_status,
            get_critical_percent,
            is_critical_unplugged,
            request_system_shutdown,
        )
    except Exception:
        return False

    status = get_battery_status()
    threshold = get_critical_percent()
    if not is_critical_unplugged(status, threshold=threshold):
        return False

    _low_battery_triggered = True
    stop_requested = True
    interrupt_pending = False
    progress["interrupted"] = True
    sync_checkpoint_context(progress)
    try:
        save_checkpoint(progress)
    except Exception:
        pass

    print(
        f"\n*** CRITICAL BATTERY: {format_status(status)} "
        f"(below {threshold}% and charger unplugged) ***",
        flush=True,
    )
    print("*** Saving all searched jobs to Excel, then shutting down… ***", flush=True)
    try:
        flush_active_save(force_excel=True)
    except Exception as exc:
        print(f"*** Excel save error during low-battery shutdown: {exc} ***", flush=True)

    request_system_shutdown(
        reason=(
            f"Low battery {format_status(status)} — LinkedIn job scrape saved to Excel"
        )
    )
    return True


def _battery_watcher_loop():
    while not _battery_watcher_stop.wait(8.0):
        if _check_low_battery_guard():
            break


def _start_battery_watcher():
    _battery_watcher_stop.clear()
    thread = threading.Thread(
        target=_battery_watcher_loop, daemon=True, name="job-battery-watcher"
    )
    thread.start()
    return thread


def _stop_battery_watcher():
    _battery_watcher_stop.set()


def check_interrupt(page, context_msg):
    if _check_low_battery_guard():
        return False
    _django_stop_requested()
    if stop_requested:
        return False
    if interrupt_pending:
        return persist_progress(context_msg)
    if page and is_offline(page):
        return handle_offline_outage(page, context_msg)
    return True


def has_title_and_company(job):
    title = (job.get("job_title") or "").strip()
    company = (job.get("company_name") or "").strip()
    if not title or not company:
        return False
    bad_titles = {
        "summary",
        "requirements",
        "minimum qualifications",
        "minimum qualifications:",
        "about the job",
        "job description",
        "responsibilities",
        "qualifications",
        "show more",
        "apply",
        "easy apply",
    }
    if title.lower().rstrip(":") in bad_titles:
        return False
    if len(title) < 3 or title.lower().endswith(":"):
        return False
    return True


def is_senior_title(text):
    return is_senior_text(text)


def extract_job_panel_text(page, max_chars=20000):
    """
    Read job detail text without Playwright body.inner_text() (hangs on AI UI).

    Prefer the right-hand job details panel; fall back to a truncated body slice.
    """
    try:
        text = page.evaluate(
            """(limit) => {
                const pick = (el) => {
                    if (!el) return '';
                    try { return (el.innerText || '').trim(); } catch (e) { return ''; }
                };
                const selectors = [
                    '.jobs-search__job-details--container',
                    '.jobs-search__job-details',
                    '.jobs-details',
                    '.job-view-layout',
                    '.jobs-details__main-content',
                    '.jobs-description__content',
                    '.jobs-box__html-content',
                    '.jobs-description',
                    '[class*="job-details"]',
                    '[class*="JobDetails"]',
                    'div.scaffold-layout__detail',
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    const t = pick(el);
                    if (t && t.length > 80) return t.slice(0, limit);
                }
                const main = document.querySelector('main') || document.body;
                const about = [...(main || document).querySelectorAll('h2, h3, div, section')]
                    .find((el) => /^about the job$/i.test((el.innerText || '').trim()));
                if (about) {
                    let root = about.parentElement;
                    for (let i = 0; i < 6 && root; i++) {
                        const t = pick(root);
                        if (t.length > 120) return t.slice(0, limit);
                        root = root.parentElement;
                    }
                }
                return pick(document.body).slice(0, limit);
            }""",
            max_chars,
        )
        return (text or "").strip()
    except Exception:
        return page_body_text(page, max_chars=max_chars)


def extract_job_fields_from_dom(page):
    """
    Read title/company/description from LinkedIn detail DOM (classic + AI).
    Avoids mistaking section headings like 'Summary' / 'Requirements' for the title.
    """
    try:
        return page.evaluate(
            """() => {
                const textOf = (el) => {
                    if (!el) return '';
                    try { return (el.innerText || el.textContent || '').trim(); } catch (e) { return ''; }
                };
                const first = (sels) => {
                    for (const sel of sels) {
                        const el = document.querySelector(sel);
                        const t = textOf(el);
                        if (t) return t.replace(/\\s+/g, ' ').trim();
                    }
                    return '';
                };
                let title = first([
                    '.job-details-jobs-unified-top-card__job-title h1',
                    '.job-details-jobs-unified-top-card__job-title a',
                    '.job-details-jobs-unified-top-card__job-title',
                    '.jobs-unified-top-card__job-title h1',
                    '.jobs-unified-top-card__job-title a',
                    '.jobs-unified-top-card__job-title',
                    'h1.t-24',
                    'h1.jobs-details-top-card__job-title',
                    '.jobs-details-top-card__job-title',
                    'div.scaffold-layout__detail h1',
                ]);
                let company = first([
                    '.job-details-jobs-unified-top-card__company-name a',
                    '.job-details-jobs-unified-top-card__company-name',
                    '.jobs-unified-top-card__company-name a',
                    '.jobs-unified-top-card__company-name',
                    '.job-details-jobs-unified-top-card__primary-description-container a',
                    '.jobs-details-top-card__company-url',
                    'div.scaffold-layout__detail a[href*="/company/"]',
                ]);
                let description = first([
                    '#job-details',
                    '.jobs-description__content',
                    '.jobs-box__html-content',
                    '.jobs-description',
                    '.jobs-description-content__text',
                    '[class*="jobs-description"]',
                ]);
                if (title.toLowerCase().startsWith('job title:')) {
                    title = title.slice(10).trim();
                }
                return { title, company, description };
            }"""
        ) or {}
    except Exception:
        return {}


def open_job_card(page, card, job_id=""):
    """Click a result card / job link. Prefer currentJobId anchors on AI UI."""
    for sel in (
        'a[href*="currentJobId="]',
        'a[href*="/jobs/view/"]',
        "a.job-card-list__title--link",
        "a.job-card-container__link",
    ):
        try:
            link = card.locator(sel).first
            if link.count() > 0:
                link.click(timeout=5000)
                return True
        except Exception:
            continue

    try:
        card.click(timeout=5000)
        return True
    except Exception:
        pass

    try:
        card.click(force=True, timeout=5000)
        return True
    except Exception:
        pass

    if job_id:
        try:
            page.evaluate(
                """(id) => {
                    const a = document.querySelector(
                        'a[href*="currentJobId=' + id + '"], a[href*="/jobs/view/' + id + '"]'
                    );
                    if (a) { a.click(); return true; }
                    return false;
                }""",
                str(job_id),
            )
            return True
        except Exception:
            return False
    return False


def wait_for_job_detail(page, job_id="", timeout_ms=12000):
    """Wait until the job detail pane shows the requested job."""
    if job_id:
        return wait_for_detail_job_id(page, job_id, timeout_ms=timeout_ms)
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        if stop_requested:
            return False
        try:
            text = extract_job_panel_text(page, max_chars=4000)
            lower = (text or "").lower()
            if len(text) > 80 and (
                "about the job" in lower
                or "apply" in lower
                or "show more" in lower
                or "job description" in lower
            ):
                return True
        except Exception:
            pass
        try:
            page.wait_for_timeout(400)
        except Exception:
            break
    return False


def is_stale_job_card(card_text, max_hours=None):
    if max_hours is None:
        max_hours = MAX_JOB_AGE_HOURS
    match = CARD_POSTED_PATTERN.search(card_text or "")
    if not match:
        return False
    hours, _ = parse_posted(match.group(0), max_hours=max_hours)
    return hours is None


RECOMMENDED_SECTION_MARKERS = (
    "top job picks for you",
    "top recommended for you",
    "top picks for you",
    "jobs you may be interested in",
    "jobs you might like",
    "more jobs for you",
    "recommended jobs",
    "jobs recommended for you",
)

# LinkedIn greys out jobs the user dismissed — not clickable / not useful to scrape.
DISABLED_JOB_MARKERS = (
    "we won't recommend this job",
    "we won\u2019t recommend this job",
    "won't recommend this job anymore",
    "won\u2019t recommend this job anymore",
    "no longer accepting applications",
)


def is_disabled_job_text(text):
    """True when LinkedIn marked this job as hidden / not recommended for you."""
    lower = (text or "").lower()
    if not lower:
        return False
    return any(marker in lower for marker in DISABLED_JOB_MARKERS)

# Keep these in sync with locate_job_cards() — used by recommended-section JS.
# LinkedIn AI /jobs/search-results/ uses hashed classes + LazyColumn.
JOB_CARD_CSS = (
    # AI search-results LazyColumn cards (2026)
    '[componentkey="SearchResultsMainContent"] [data-display-contents="true"] > div, '
    '[data-component-type="LazyColumn"][componentkey="SearchResultsMainContent"] '
    '[data-display-contents="true"] > div, '
    "div._51df3a07, "
    'div[componentkey^="job-card-component-ref-"], '
    'div[role="button"][componentkey^="job-card"], '
    'div[componentkey^="job-card"], '
    "li.jobs-collection__list-item, "
    "div.jobs-collection__list-item, "
    ".jobs-collections-module__job-card, "
    ".jobs-collections-module__job-card-container, "
    # Classic /jobs/search/ UI
    ".job-card-container, "
    "li.jobs-search-results__list-item, "
    "li.jobs-search-results-list__list-item, "
    "div.job-card-list__entity-lockup, "
    "[data-occludable-job-id], "
    "[data-job-id], "
    "li.scaffold-layout__list-item, "
    ".scaffold-layout__list-container > li, "
    "ul.scaffold-layout__list > li, "
    ".jobs-search-results-list li, "
    "div.job-card-list, "
    "div[data-view-name='job-card']"
)

JOB_CARD_SELECTORS = (
    # AI /jobs/search-results/ LazyColumn (stable structure; hashed class may change)
    '[componentkey="SearchResultsMainContent"] [data-display-contents="true"] > div',
    '[data-component-type="LazyColumn"][componentkey="SearchResultsMainContent"] '
    '[data-display-contents="true"] > div',
    "div._51df3a07.c2e40184",
    "div._51df3a07",
    'div[componentkey^="job-card-component-ref-"]',
    'div[role="button"][componentkey^="job-card"]',
    'div[componentkey^="job-card"]',
    "li.jobs-collection__list-item",
    "div.jobs-collection__list-item",
    ".jobs-collections-module__job-card",
    ".jobs-collections-module__job-card-container",
    # Classic /jobs/search/ UI
    ".job-card-container",
    "li.jobs-search-results__list-item",
    "li.jobs-search-results-list__list-item",
    "div.job-card-list__entity-lockup",
    "[data-occludable-job-id]",
    "[data-job-id]",
    "li.scaffold-layout__list-item",
    ".scaffold-layout__list-container > li",
    "ul.scaffold-layout__list > li",
    ".jobs-search-results-list li",
    "div.job-card-list",
    "div[data-view-name='job-card']",
    "a.job-card-list__title--link",
    "a.job-card-container__link",
    'a[href*="/jobs/search-results/"][href*="currentJobId="]',
    'a[href*="currentJobId="]',
    ".scaffold-layout__list li:has(a[href*='/jobs/view/'])",
    ".jobs-search-results-list li:has(a[href*='/jobs/view/'])",
    "li:has(a[href*='/jobs/view/'])",
    "li:has(a[href*='currentJobId='])",
)

# Mark AI / classic job cards so Playwright can locate them reliably.
# Prefer stable job links (currentJobId /jobs/view/) — hashed CSS classes change often.
_MARK_AI_JOB_CARDS_JS = """() => {
    const isDisabledJob = (el) => {
        if (!el) return false;
        let text = '';
        try { text = (el.innerText || '').toLowerCase(); } catch (e) { return false; }
        return (
            text.includes("won't recommend this job") ||
            text.includes("won\\u2019t recommend this job") ||
            text.includes('no longer accepting applications')
        );
    };

    const extractId = (href) => {
        if (!href) return null;
        let m = href.match(/[?&]currentJobId=(\\d{6,})/);
        if (m) return m[1];
        m = href.match(/\\/jobs\\/view\\/(\\d{6,})/);
        return m ? m[1] : null;
    };

    const pickCard = (anchor) => {
        let el = anchor;
        let best = null;
        for (let i = 0; i < 14 && el; i++) {
            el = el.parentElement;
            if (!el || el === document.body || el === document.documentElement) break;
            const tag = el.tagName;
            if (tag === 'MAIN' || tag === 'NAV' || tag === 'HEADER' || tag === 'FOOTER') break;
            let text = '';
            try { text = (el.innerText || '').trim(); } catch (e) { text = ''; }
            if (text.length < 12 || text.length > 3500) continue;
            const rect = el.getBoundingClientRect();
            if (rect.height < 36 || rect.height > 720 || rect.width < 120) continue;
            best = el;
            // Prefer LI / role=listitem / known job-card wrappers.
            const role = (el.getAttribute('role') || '').toLowerCase();
            const ck = (el.getAttribute('componentkey') || el.getAttribute('componentKey') || '');
            if (
                tag === 'LI' ||
                role === 'listitem' ||
                role === 'button' ||
                ck.toLowerCase().includes('job-card') ||
                el.hasAttribute('data-occludable-job-id') ||
                el.hasAttribute('data-job-id')
            ) {
                return el;
            }
            // display-contents wrapper → use first meaningful child
            if (el.getAttribute('data-display-contents') === 'true') {
                const child = [...el.children].find((c) => {
                    if (!c || c.tagName !== 'DIV') return false;
                    const t = (c.innerText || '').trim();
                    return t.length >= 12;
                });
                if (child) return child;
            }
        }
        return best || anchor;
    };

    document.querySelectorAll('[data-pm-job-card="1"]').forEach((el) => {
        el.removeAttribute('data-pm-job-card');
        el.removeAttribute('data-pm-job-id');
    });

    const seen = new Set();
    let marked = 0;
    const root =
        document.querySelector('[componentkey="SearchResultsMainContent"]') ||
        document.querySelector('[data-component-type="LazyColumn"][componentkey*="SearchResults"]') ||
        document.querySelector('main') ||
        document.body;

    const anchors = root.querySelectorAll(
        'a[href*="currentJobId="], a[href*="/jobs/view/"]'
    );
    for (const a of anchors) {
        const id = extractId(a.getAttribute('href') || '');
        if (!id || seen.has(id)) continue;
        const card = pickCard(a);
        if (!card || isDisabledJob(card)) continue;
        seen.add(id);
        card.setAttribute('data-pm-job-card', '1');
        card.setAttribute('data-pm-job-id', id);
        marked += 1;
    }

    // Fallback: LazyColumn display-contents children (no stable link yet).
    if (!marked) {
        const wrappers = root.querySelectorAll('[data-display-contents="true"]');
        for (const wrap of wrappers) {
            const card = [...wrap.children].find((el) => {
                if (!el || el.tagName !== 'DIV') return false;
                if (el.getAttribute('role') === 'presentation') return false;
                const text = (el.innerText || '').trim();
                return text.length >= 12;
            });
            if (!card) continue;
            if (isDisabledJob(card)) continue;
            card.setAttribute('data-pm-job-card', '1');
            marked += 1;
        }
    }

    // Last resort: previously observed hashed card class.
    if (!marked) {
        root.querySelectorAll('div._51df3a07').forEach((el) => {
            const text = (el.innerText || '').trim();
            if (text.length < 12) return;
            if (isDisabledJob(el)) return;
            el.setAttribute('data-pm-job-card', '1');
            marked += 1;
        });
    }
    return marked;
}"""

# Shared browser-side helpers for finding LinkedIn's recommended block.
_RECOMMENDED_JS_MARKERS = json.dumps(list(RECOMMENDED_SECTION_MARKERS))
_JOB_CARD_CSS_JS = json.dumps(JOB_CARD_CSS)

_FIND_RECOMMENDED_HEADING_TOP_JS = f"""() => {{
    const markers = {_RECOMMENDED_JS_MARKERS};
    // Only scan headings / strong labels — full div/li scan freezes LinkedIn AI pages.
    const nodes = document.querySelectorAll(
        'h1, h2, h3, h4, h5, [role="heading"], strong'
    );
    for (const el of nodes) {{
        let text = '';
        try {{
            text = (el.innerText || '').trim().toLowerCase();
        }} catch (e) {{
            continue;
        }}
        if (!text || text.length > 120) continue;
        if (!markers.some((m) => text.includes(m))) continue;
        const rect = el.getBoundingClientRect();
        if (rect.height <= 0 && rect.width <= 0) continue;
        return rect.top + window.scrollY;
    }}
    return null;
}}"""

_COUNT_CARDS_BEFORE_RECOMMENDED_JS = f"""() => {{
    const markers = {_RECOMMENDED_JS_MARKERS};
    let headingTop = null;
    const nodes = document.querySelectorAll(
        'h1, h2, h3, h4, h5, [role="heading"], strong'
    );
    for (const el of nodes) {{
        let text = '';
        try {{
            text = (el.innerText || '').trim().toLowerCase();
        }} catch (e) {{
            continue;
        }}
        if (!text || text.length > 120) continue;
        if (!markers.some((m) => text.includes(m))) continue;
        const rect = el.getBoundingClientRect();
        if (rect.height <= 0 && rect.width <= 0) continue;
        headingTop = rect.top + window.scrollY;
        break;
    }}

    const cards = [...document.querySelectorAll('[data-pm-job-card="1"]')];
    if (!cards.length) {{
        // Fall back to CSS only if marks missing.
        try {{
            cards.push(...document.querySelectorAll({_JOB_CARD_CSS_JS}));
        }} catch (e) {{}}
    }}
    if (headingTop == null) return cards.length;
    return cards.filter((card) => {{
        const top = card.getBoundingClientRect().top + window.scrollY;
        return top + 8 < headingTop;
    }}).length;
}}"""

_RECOMMENDED_DOMINATES_JS = f"""() => {{
    const markers = {_RECOMMENDED_JS_MARKERS};
    let headingTop = null;
    const nodes = document.querySelectorAll(
        'h1, h2, h3, h4, h5, [role="heading"], strong'
    );
    for (const el of nodes) {{
        let text = '';
        try {{
            text = (el.innerText || '').trim().toLowerCase();
        }} catch (e) {{
            continue;
        }}
        if (!text || text.length > 120) continue;
        if (!markers.some((m) => text.includes(m))) continue;
        const rect = el.getBoundingClientRect();
        if (rect.height <= 0 && rect.width <= 0) continue;
        headingTop = rect.top + window.scrollY;
        break;
    }}
    if (headingTop == null) return false;

    let cards = [...document.querySelectorAll('[data-pm-job-card="1"]')];
    if (!cards.length) {{
        try {{
            cards = [...document.querySelectorAll({_JOB_CARD_CSS_JS})];
        }} catch (e) {{
            cards = [];
        }}
    }}
    if (!cards.length) {{
        return false;
    }}

    const cardsBefore = cards.filter((card) => {{
        const top = card.getBoundingClientRect().top + window.scrollY;
        return top + 8 < headingTop;
    }}).length;
    return cardsBefore <= 2;
}}"""

_DIAGNOSE_JOB_CARDS_JS = f"""() => {{
    const sels = {_JOB_CARD_CSS_JS}.split(',').map((s) => s.trim());
    const extra = [
        '[componentkey="SearchResultsMainContent"]',
        '[data-component-type="LazyColumn"]',
        '[data-display-contents="true"]',
        '[data-pm-job-card="1"]',
        'div._51df3a07',
        'div[componentkey^="job-card"]',
        'div[componentkey*="job-card"]',
        'a[href*="currentJobId="]',
        'a[href*="/jobs/search-results/"]',
        'a[href*="/jobs/view/"]',
        '[data-job-id]',
        '[data-occludable-job-id]',
    ];
    const counts = {{}};
    for (const s of [...sels, ...extra]) {{
        try {{ counts[s] = document.querySelectorAll(s).length; }}
        catch (e) {{ counts[s] = -1; }}
    }}
    const links = document.querySelectorAll(
        'a[href*="/jobs/view/"], a[href*="currentJobId="]'
    ).length;
    const componentKeys = [...document.querySelectorAll('[componentkey], [componentKey]')]
        .slice(0, 12)
        .map((el) => el.getAttribute('componentkey') || el.getAttribute('componentKey') || '');
    const body = ((document.body && document.body.innerText) || '').slice(0, 500);
    return {{
        counts,
        links,
        componentKeys,
        url: location.href,
        title: document.title,
        body,
    }};
}}"""


RESULT_COUNT_PATTERN = re.compile(
    r"([\d,]+)\s*\+?\s*results?",
    re.I,
)

# LinkedIn f_E experience codes: 1=Internship, 2=Entry level, 3=Associate, …
LINKEDIN_ENTRY_LEVEL_F_E = "2"

KEEP_JOB_FILTER_MARKERS = (
    "past ",
    "any time",
    "last hour",
    "last 24",
    "past 24",
    "past week",
    "past month",
    "date posted",
    "entry level",
    "entry-level",
    "100 km",
    "most relevant",
)

# Exact chips we keep. Everything else (Remote, Easy Apply, AI/ML, skills…) is cleared.
KEEP_JOB_FILTER_EXACT = {
    "jobs",
    "job",
}

STICKY_JOB_FILTER_MARKERS = (
    "under 10 applicants",
    "in my network",
    "in your network",
    "easy apply",
    "has verifications",
    "fair chance",
    "actively hiring",
    "remote",
    "hybrid",
    "on-site",
    "onsite",
    "ai/ml",
    "full stack",
    "fullstack",
    "llm",
    "gen ai",
    "experience level",
    "employment type",
    "company",
    "internship",
    "entry level",
    "mid-senior",
    "director",
)


def page_has_no_jobs(page):
    try:
        body = page_body_text(page, max_chars=2500).lower()
    except Exception:
        return False
    return (
        "no matching jobs found" in body
        or "no results found" in body
        or "unfortunately, we couldn't find" in body
        or "we couldn't find a match" in body
        or "0 results" in body[:2000]
    )


def page_shows_similar_not_exact(page):
    """True when LinkedIn AI filled results with similar (not exact) jobs."""
    body = page_body_text(page).lower()
    return (
        "share similar criteria" in body
        or "trouble finding exact matches" in body
        or "results that share similar" in body
        or "couldn't find exact matches" in body
        or "could not find exact matches" in body
    )


def page_body_text(page, max_chars=4000):
    """
    Read a truncated slice of visible page text.

    Never use Playwright body.inner_text() on LinkedIn AI pages — it can hang
    forever on huge React trees (and matches the "stuck after N results" symptom).
    """
    try:
        return page.evaluate(
            """(limit) => {
                const text = (document.body && document.body.innerText) || '';
                return text.slice(0, limit || 4000);
            }""",
            max_chars,
        ) or ""
    except Exception:
        return ""


def page_has_recommended_section(page):
    body = page_body_text(page).lower()
    if any(marker in body for marker in RECOMMENDED_SECTION_MARKERS):
        return True
    try:
        return page.evaluate(_FIND_RECOMMENDED_HEADING_TOP_JS) is not None
    except Exception:
        return False


_DISMISS_FOOTER_SHEET_JS = """() => {
    const markers = [
        'visit our help center',
        'manage your account and privacy',
        'recommendation transparency',
        'linkedin corporation',
        'select language',
    ];
    const looksLikeFooterSheet = (el) => {
        let text = '';
        try { text = (el.innerText || '').toLowerCase(); } catch (e) { return false; }
        if (!text || text.length > 12000) return false;
        const hits = markers.filter((m) => text.includes(m)).length;
        if (hits < 2) return false;
        const rect = el.getBoundingClientRect();
        return rect.height > 60 && rect.width > 180;
    };
    const clickClose = (root) => {
        const closeSels = [
            'button[aria-label*="Close" i]',
            'button[aria-label*="Dismiss" i]',
            'button.artdeco-modal__dismiss',
            '[data-test-modal-close-btn]',
            'button[data-test-modal-close-btn]',
        ];
        for (const sel of closeSels) {
            const btn = root.querySelector(sel);
            if (btn) { btn.click(); return true; }
        }
        for (const btn of root.querySelectorAll('button')) {
            const label = (btn.getAttribute('aria-label') || '').toLowerCase();
            const txt = (btn.innerText || '').trim();
            if (
                label.includes('close') ||
                label.includes('dismiss') ||
                txt === '×' ||
                txt === 'X' ||
                txt === '✕'
            ) {
                btn.click();
                return true;
            }
        }
        return false;
    };

    const candidates = [
        ...document.querySelectorAll(
            '[role="dialog"], .artdeco-modal, aside, div[class*="modal"], div[class*="sheet"]'
        ),
        ...document.querySelectorAll('div, section, aside'),
    ];
    for (const el of candidates) {
        if (!looksLikeFooterSheet(el)) continue;
        if (clickClose(el)) return true;
    }
    return false;
}"""


def dismiss_linkedin_footer_sheet(page):
    """Close LinkedIn footer/help bottom sheet that blocks job list clicks."""
    closed = False
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)
    except Exception:
        pass
    try:
        if page.evaluate(_DISMISS_FOOTER_SHEET_JS):
            closed = True
            print("  Closed LinkedIn footer/help sheet.")
            page.wait_for_timeout(400)
    except Exception:
        pass
    return closed


def dismiss_job_search_overlays(page):
    """Close AI-powered job search popup / banners that block results."""
    closed = False
    if dismiss_linkedin_footer_sheet(page):
        closed = True

    # Prefer closing the specific AI job-search notice ("You're now using AI-powered...").
    try:
        ai_notice = page.locator(
            "text=/you.?re now using ai-powered job search/i"
        ).first
        if ai_notice.count() > 0:
            # Close button is usually an X near the notice.
            container = ai_notice.locator(
                "xpath=ancestor::*[self::div or self::section][1]"
            )
            for close_sel in (
                'button[aria-label*="Dismiss" i]',
                'button[aria-label*="Close" i]',
                'button[aria-label*="dismiss" i]',
                "button.artdeco-button--circle",
                "button",
            ):
                try:
                    btn = container.locator(close_sel).last
                    if btn.count() > 0:
                        btn.click(timeout=1200)
                        closed = True
                        page.wait_for_timeout(400)
                        print("  Closed AI-powered job search popup.")
                        break
                except Exception:
                    continue
            if not closed:
                # Fallback: click any nearby X via JS.
                try:
                    page.evaluate(
                        """() => {
                            const text = (el) => (el.innerText || '').toLowerCase();
                            const nodes = [...document.querySelectorAll('div,section,aside')];
                            for (const el of nodes) {
                                if (!text(el).includes('ai-powered job search')) continue;
                                const btn = el.querySelector(
                                    'button[aria-label*="Dismiss"], button[aria-label*="Close"], button'
                                );
                                if (btn) { btn.click(); return true; }
                            }
                            return false;
                        }"""
                    )
                    closed = True
                    print("  Closed AI-powered job search popup.")
                    page.wait_for_timeout(400)
                except Exception:
                    pass
    except Exception:
        pass

    selectors = (
        'button[aria-label="Dismiss"]',
        'button[aria-label="Close"]',
        'button[aria-label*="Dismiss"]',
        'button[aria-label*="Close"]',
        "button.artdeco-modal__dismiss",
        "[data-test-modal-close-btn]",
        ".artdeco-toast-item__dismiss",
        'button:has-text("Dismiss")',
        'button:has-text("Got it")',
        'button:has-text("Not now")',
        'button:has-text("No thanks")',
        'button:has-text("Cancel")',
    )
    for selector in selectors:
        try:
            loc = page.locator(selector)
            count = min(loc.count(), 4)
        except Exception:
            continue
        for idx in range(count):
            try:
                loc.nth(idx).click(timeout=800)
                closed = True
                page.wait_for_timeout(250)
            except Exception:
                continue

    # Footer/help sheet often reappears after other dismissals.
    if dismiss_linkedin_footer_sheet(page):
        closed = True
    return closed


def clear_sticky_job_filters(page):
    """Remove LinkedIn sticky chips except Jobs + date-posted filters."""
    pill_selectors = (
        "button.search-reusables__filter-pill-button",
        "button.artdeco-pill",
        ".search-reusables__primary-filter button",
        ".jobs-search-filter-pill button",
        'button[aria-pressed="true"]',
        ".artdeco-hoverable-content button",
    )
    removed_labels = []
    for _ in range(12):
        removed = False
        for selector in pill_selectors:
            try:
                pills = page.locator(selector)
                count = pills.count()
            except Exception:
                continue
            for idx in range(min(count, 30)):
                try:
                    pill = pills.nth(idx)
                    text = (pill.inner_text(timeout=800) or "").strip().lower().replace("\n", " ")
                except Exception:
                    continue
                if not text or len(text) > 60:
                    continue
                exact = text.strip()
                if exact in KEEP_JOB_FILTER_EXACT:
                    continue
                if any(keep in text for keep in KEEP_JOB_FILTER_MARKERS):
                    continue
                # Drop sticky skill/experience/easy-apply chips and similar leftovers.
                should_remove = True
                try:
                    close = pill.locator(
                        '[aria-label*="Remove" i], [aria-label*="Dismiss" i], '
                        'button[aria-label*="Remove" i], svg'
                    ).last
                    if close.count() > 0:
                        close.click(timeout=1200)
                    else:
                        pill.click(timeout=1200)
                    removed = True
                    removed_labels.append(exact[:40])
                    page.wait_for_timeout(500)
                    break
                except Exception:
                    continue
            if removed:
                break
        if not removed:
            break
    if removed_labels:
        print(f"  Cleared sticky filters: {', '.join(removed_labels[:8])}")


_ENSURE_ENTRY_LEVEL_JS = """() => {
    const norm = (s) => (s || '').toLowerCase().replace(/\\s+/g, ' ').trim();
    const isSelectedChip = (el) => {
        if (!el) return false;
        const text = norm(el.innerText);
        if (text !== 'entry level' && text !== 'entry-level' && !text.startsWith('entry level')) {
            return false;
        }
        if (el.getAttribute('aria-pressed') === 'true') return true;
        if (el.classList.contains('artdeco-pill--selected')) return true;
        const cls = (el.className || '').toLowerCase();
        if (cls.includes('selected') || cls.includes('active')) return true;
        return false;
    };
    const chips = [...document.querySelectorAll('button')];
    for (const chip of chips) {
        if (isSelectedChip(chip)) return 'active';
    }
    try {
        const fe = (new URLSearchParams(location.search).get('f_E') || '').split(',');
        if (fe.includes('2')) {
            const roots = [
                document.querySelector('.search-reusables__filters-bar'),
                document.querySelector('.jobs-search__filters'),
                document.querySelector('main'),
            ].filter(Boolean);
            for (const root of roots) {
                const text = norm(root.innerText || '').slice(0, 2500);
                if (text.includes('entry level') || text.includes('entry-level')) {
                    return 'active';
                }
            }
        }
    } catch (e) {}
    return 'missing';
}"""

_APPLY_ENTRY_LEVEL_OPEN_JS = """() => {
    const norm = (s) => (s || '').toLowerCase().replace(/\\s+/g, ' ').trim();
    const classic = document.querySelector('#searchFilter_experienceLevel');
    if (classic) {
        classic.click();
        return 'classic';
    }
    for (const btn of document.querySelectorAll('button, [role="button"]')) {
        const text = norm(btn.innerText);
        const aria = norm(btn.getAttribute('aria-label') || '');
        if (text === 'entry level' || text === 'entry-level') continue;
        if (
            text === 'experience level' ||
            aria === 'experience level filter' ||
            aria.startsWith('experience level')
        ) {
            btn.click();
            return 'ai';
        }
    }
    return '';
}"""

_APPLY_ENTRY_LEVEL_SELECT_JS = """() => {
    const norm = (s) => (s || '').toLowerCase().replace(/\\s+/g, ' ').trim();
    const inputs = document.querySelectorAll(
        'input[type="checkbox"], input[type="radio"]'
    );
    for (const inp of inputs) {
        if (String(inp.value) === '2') {
            if (!inp.checked) inp.click();
            return 'input';
        }
    }
    for (const el of document.querySelectorAll('label, span, div, li, button')) {
        const text = norm(el.innerText);
        if (text !== 'entry level' && text !== 'entry-level') continue;
        const inp = el.querySelector('input[type="checkbox"], input[type="radio"]');
        if (inp) {
            if (!inp.checked) inp.click();
            return 'label_input';
        }
        el.click();
        return 'label';
    }
    return '';
}"""

_APPLY_ENTRY_LEVEL_SUBMIT_JS = """() => {
    const norm = (s) => (s || '').toLowerCase().replace(/\\s+/g, ' ').trim();
    for (const btn of document.querySelectorAll('button')) {
        const text = norm(btn.innerText);
        if (
            text === 'show results' ||
            text === 'apply' ||
            text.startsWith('show ') ||
            text === 'done'
        ) {
            btn.click();
            return text;
        }
    }
    return '';
}"""


def entry_level_filter_active(page):
    try:
        return page.evaluate(_ENSURE_ENTRY_LEVEL_JS) == "active"
    except Exception:
        return False


def apply_entry_level_experience_filter(page):
    """Open Experience level UI, select Entry level, submit."""
    for attempt in range(4):
        if entry_level_filter_active(page):
            return True

        opened = False
        try:
            for selector in (
                "#searchFilter_experienceLevel",
                'button[aria-label="Experience level filter"]',
                'button[aria-label*="Experience level" i]',
            ):
                btn = page.locator(selector).first
                if btn.count() == 0:
                    continue
                try:
                    btn.scroll_into_view_if_needed(timeout=2500)
                    btn.click(timeout=4000)
                    opened = True
                    break
                except Exception:
                    continue
        except Exception:
            pass

        if not opened:
            try:
                opened = bool(page.evaluate(_APPLY_ENTRY_LEVEL_OPEN_JS))
            except Exception:
                opened = False

        if not opened:
            page.wait_for_timeout(700)
            continue

        page.wait_for_timeout(900)

        selected = False
        try:
            for selector in (
                'label:has-text("Entry level")',
                'label:has-text("Entry-level")',
                'input[type="checkbox"][value="2"]',
                'input[type="radio"][value="2"]',
                '[data-filter-value="2"]',
            ):
                opt = page.locator(selector).first
                if opt.count() == 0:
                    continue
                try:
                    opt.click(timeout=3000)
                    selected = True
                    break
                except Exception:
                    continue
        except Exception:
            pass

        if not selected:
            try:
                selected = bool(page.evaluate(_APPLY_ENTRY_LEVEL_SELECT_JS))
            except Exception:
                selected = False

        page.wait_for_timeout(500)

        try:
            for show_sel in (
                'button:has-text("Show results")',
                'button:has-text("Apply")',
                'button:has-text("Done")',
            ):
                show = page.locator(show_sel).first
                if show.count() == 0:
                    continue
                try:
                    if show.is_visible():
                        show.click(timeout=4000)
                        break
                except Exception:
                    continue
            else:
                page.evaluate(_APPLY_ENTRY_LEVEL_SUBMIT_JS)
        except Exception:
            pass

        try:
            page.wait_for_load_state("domcontentloaded", timeout=20000)
        except Exception:
            pass
        page.wait_for_timeout(1200)

        if entry_level_filter_active(page):
            return True

    return entry_level_filter_active(page)


def reload_with_entry_level_url(page, keywords_query, location, time_filter, start=0):
    """Reload search with f_E=2 (AI URL, then classic /jobs/search/ fallback)."""
    urls = (
        build_job_search_results_url(keywords_query, location, time_filter, start=start),
        build_classic_job_search_url(keywords_query, location, time_filter, start=start),
    )
    for search_url in urls:
        if not open_page_with_retry(page, search_url, "reloading with Entry level filter"):
            continue
        page.wait_for_timeout(1500)
        dismiss_job_search_overlays(page)
        if entry_level_filter_active(page):
            return True
        if apply_entry_level_experience_filter(page):
            return True
    return entry_level_filter_active(page)


def _search_sort_distance_ok(page):
    try:
        return page.evaluate(
            """([sortBy, minDistance]) => {
                const norm = (s) => (s || '').toLowerCase().replace(/\\s+/g, ' ').trim();
                let sortOk = false;
                let distOk = false;
                try {
                    const params = new URLSearchParams(location.search);
                    sortOk = params.get('sortBy') === sortBy;
                    const d = parseFloat(params.get('distance') || '0');
                    distOk = d >= minDistance - 0.01;
                } catch (e) {}
                for (const el of document.querySelectorAll('button, [role="button"], label')) {
                    const t = norm(el.innerText || el.textContent || '');
                    if (t.includes('most relevant')) sortOk = true;
                    if (
                        t === `${minDistance} km` ||
                        t.startsWith(`${minDistance} km`) ||
                        t.includes(`${minDistance} km`) ||
                        t.includes(`${minDistance}km`)
                    ) {
                        distOk = true;
                    }
                }
                return { sortOk, distOk };
            }""",
            [JOB_SEARCH_SORT_BY, JOB_SEARCH_DISTANCE_KM],
        )
    except Exception:
        return {"sortOk": False, "distOk": False}


def _click_distance_option(page):
    """Open Distance filter and pick 100 km (LinkedIn jobs UI)."""
    km = int(JOB_SEARCH_DISTANCE_KM)
    open_selectors = (
        f'button:has-text("{km} km")',
        'button:has-text("Distance")',
        'button[aria-label*="Distance" i]',
        'button:has-text("0 km")',
        'button:has-text("25 km")',
        'button:has-text("40 km")',
        'button:has-text("50 km")',
        'button:has-text("80 km")',
        'button:has-text("Exact location")',
        'button:has-text("Anywhere")',
        '[data-test-distance-filter]',
        'button.artdeco-pill:has-text("km")',
    )
    for selector in open_selectors:
        btn = page.locator(selector).first
        if btn.count() == 0:
            continue
        try:
            text = (btn.inner_text(timeout=1000) or "").strip().lower()
            if f"{km} km" in text or f"{km}km" in text.replace(" ", ""):
                return True
            btn.click(timeout=3000)
            page.wait_for_timeout(450)
            for opt_sel in (
                f'label:has-text("{km} km")',
                f'span:has-text("{km} km")',
                f'div[role="option"]:has-text("{km} km")',
                f'button:has-text("{km} km")',
                f'li:has-text("{km} km")',
                f'[role="menuitem"]:has-text("{km} km")',
                f'[role="radio"]:has-text("{km} km")',
                f'input[type="radio"][value="{km}"], input[type="radio"][value="{float(km)}"]',
            ):
                opt = page.locator(opt_sel).first
                if opt.count() == 0:
                    continue
                try:
                    opt.click(timeout=2000)
                    page.wait_for_timeout(700)
                    return True
                except Exception:
                    continue
            # Some LinkedIn builds use a slider / listitem click via JS text match.
            clicked = page.evaluate(
                """(km) => {
                    const want = `${km} km`;
                    const nodes = Array.from(document.querySelectorAll(
                        'label, span, div, li, button, [role="option"], [role="menuitem"], [role="radio"]'
                    ));
                    for (const n of nodes) {
                        const t = (n.innerText || n.textContent || '').replace(/\\s+/g, ' ').trim();
                        if (t === want || t.startsWith(want)) {
                            n.click();
                            return true;
                        }
                    }
                    return false;
                }""",
                km,
            )
            if clicked:
                page.wait_for_timeout(700)
                return True
        except Exception:
            continue
    return False


def apply_search_sort_and_distance(page):
    """Set Sort by = Most relevant and Distance = 100 km on LinkedIn jobs UI."""
    state = _search_sort_distance_ok(page)
    if state.get("sortOk") and state.get("distOk"):
        return True

    if not state.get("sortOk"):
        for selector in (
            'button:has-text("Most recent")',
            'button[aria-label*="Sort by" i]',
            'button:has-text("Sort by")',
        ):
            btn = page.locator(selector).first
            if btn.count() == 0:
                continue
            try:
                btn.click(timeout=3000)
                page.wait_for_timeout(500)
                for opt_sel in (
                    'label:has-text("Most relevant")',
                    'span:has-text("Most relevant")',
                    'div[role="option"]:has-text("Most relevant")',
                    'button:has-text("Most relevant")',
                ):
                    opt = page.locator(opt_sel).first
                    if opt.count() == 0:
                        continue
                    opt.click(timeout=2000)
                    page.wait_for_timeout(600)
                    break
                break
            except Exception:
                continue

    state = _search_sort_distance_ok(page)
    if not state.get("distOk"):
        _click_distance_option(page)

    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(800)
    state = _search_sort_distance_ok(page)
    return state.get("sortOk") and state.get("distOk")


def reload_with_sort_and_distance_url(page, keywords_query, location, time_filter, start=0):
    """Force distance=100 km (+ Most relevant) via search URL when UI clicks fail."""
    for builder in (
        build_job_search_results_url,
        build_classic_job_search_url,
    ):
        try:
            url = builder(keywords_query, location, time_filter, start=start)
            if f"distance=" not in url and (location or "").strip():
                sep = "&" if "?" in url else "?"
                url = f"{url}{sep}distance={float(JOB_SEARCH_DISTANCE_KM)}"
            if not open_page_with_retry(page, url, "applying 100 km distance via URL"):
                continue
            pause_search(page)
            prepare_job_results_page(page)
            if _search_sort_distance_ok(page).get("distOk"):
                return True
            if apply_search_sort_and_distance(page):
                return True
        except Exception:
            continue
    return False


def ensure_search_sort_and_distance(
    page, keywords_query="", location="", time_filter="", start=0
):
    """Ensure Most relevant sort and 100 km around the location for every search."""
    if apply_search_sort_and_distance(page):
        print(
            f"  Search preferences: Most relevant sort, "
            f"{JOB_SEARCH_DISTANCE_KM} km around location."
        )
        return True

    if keywords_query and (location or "").strip():
        if reload_with_sort_and_distance_url(
            page, keywords_query, location, time_filter, start=start
        ):
            print(
                f"  Applied {JOB_SEARCH_DISTANCE_KM} km around location via search URL."
            )
            return True

    state = _search_sort_distance_ok(page)
    parts = []
    if state.get("sortOk"):
        parts.append("Most relevant")
    if state.get("distOk"):
        parts.append(f"{JOB_SEARCH_DISTANCE_KM} km")
    if parts:
        print(f"  Search preferences partially set: {', '.join(parts)}.")
    else:
        print(
            f"  WARNING: Could not confirm sort={JOB_SEARCH_SORT_BY} / "
            f"distance={JOB_SEARCH_DISTANCE_KM} km around location."
        )
    return bool(state.get("sortOk") and state.get("distOk"))


def ensure_entry_level_experience_filter(
    page, keywords_query="", location="", time_filter="", start=0
):
    """
    Ensure LinkedIn Experience level = Entry level (fresher-friendly search).

    URL f_E=2 alone is not trusted on /jobs/search-results/ — verify the UI chip.
    """
    if entry_level_filter_active(page):
        print("  Experience filter active: Entry level.")
        return True

    if apply_entry_level_experience_filter(page):
        print("  Applied LinkedIn filter: Experience level -> Entry level.")
        return True

    if keywords_query and reload_with_entry_level_url(
        page, keywords_query, location, time_filter, start=start
    ):
        print("  Applied Entry level filter via search URL reload.")
        if apply_entry_level_experience_filter(page):
            print("  Confirmed Entry level filter in UI.")
        return entry_level_filter_active(page)

    print("  WARNING: Could not confirm Entry level filter in LinkedIn UI.")
    return False


def prepare_job_results_page(page, apply_entry_level=False):
    """Dismiss AI popups and clear sticky skill filters before scraping cards."""
    dismiss_job_search_overlays(page)
    clear_sticky_job_filters(page)
    if apply_entry_level:
        ensure_entry_level_experience_filter(page)


def diagnose_missing_job_cards(page):
    try:
        info = page.evaluate(_DIAGNOSE_JOB_CARDS_JS)
    except Exception as exc:
        print(f"  Debug: could not inspect page ({exc})")
        return
    print(f"  Debug: page={info.get('url')}")
    print(f"  Debug: title={info.get('title')}")
    print(f"  Debug: job links={info.get('links')}")
    keys = info.get("componentKeys") or []
    if keys:
        print(f"  Debug: componentkey sample={keys[:6]}")
    counts = info.get("counts") or {}
    nonzero = {k: v for k, v in counts.items() if v}
    if nonzero:
        print(f"  Debug: selector hits={nonzero}")
    else:
        print("  Debug: no known job-card selectors matched.")
    body = (info.get("body") or "").replace("\n", " ").strip()
    if body:
        print(f"  Debug: body sample={body[:220]}")


def parse_search_result_count(page):
    """Read LinkedIn's total search result count from the results header."""
    selectors = (
        ".jobs-search-results-list__subtitle",
        ".jobs-search-results-list__text",
        "small.jobs-search-results-list__text",
        ".t-12.t-black--light.t-normal",
        "div.jobs-search-results-list__subtitle",
        ".jobs-search-results-list__text--display",
    )
    for selector in selectors:
        try:
            loc = page.locator(selector)
            count = loc.count()
        except Exception:
            continue
        for idx in range(min(count, 6)):
            try:
                text = (loc.nth(idx).inner_text() or "").strip()
            except Exception:
                continue
            match = RESULT_COUNT_PATTERN.search(text)
            if match:
                try:
                    return int(match.group(1).replace(",", ""))
                except ValueError:
                    continue

    body = page_body_text(page)
    # Prefer the first "N results" near the top of the page body.
    match = RESULT_COUNT_PATTERN.search(body[:2500] if body else "")
    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def recommended_section_dominates(page):
    """
    True when LinkedIn has exhausted real search hits and is showing
    'Top job picks / Top recommended for you' as the main list content.
    """
    if not page_has_recommended_section(page):
        return False

    try:
        return bool(page.evaluate(_RECOMMENDED_DOMINATES_JS))
    except Exception:
        # Fallback: if the marker appears early in page text, treat as end of search.
        body = page_body_text(page).lower()
        for marker in RECOMMENDED_SECTION_MARKERS:
            pos = body.find(marker)
            if pos != -1 and pos < 3500:
                return True
        return False


def count_search_result_cards(page):
    """Count job cards that appear before LinkedIn's recommended section."""
    try:
        return int(page.evaluate(_COUNT_CARDS_BEFORE_RECOMMENDED_JS))
    except Exception:
        return locate_job_cards(page).count()


def card_is_below_recommended(page, card):
    """True when this card sits under the recommended / Top picks heading."""
    try:
        heading_top = page.evaluate(_FIND_RECOMMENDED_HEADING_TOP_JS)
        if heading_top is None:
            return False
        box = card.bounding_box()
        if not box:
            return False
        scroll_y = page.evaluate("() => window.scrollY") or 0
        return (box["y"] + scroll_y + 8) >= heading_top
    except Exception:
        return False


def wait_for_job_results(page, max_attempts=10):
    """Wait for cards to load before treating a search as empty."""
    prepare_job_results_page(page)
    for attempt in range(max_attempts):
        if not check_interrupt(page, "while waiting for job results"):
            return "interrupted"
        if attempt in (3, 6):
            prepare_job_results_page(page)
        cards = locate_job_cards(page)
        try:
            count = cards.count()
        except Exception:
            count = 0
        if count > 0:
            return "ready"
        # Result header alone is NOT enough — keep waiting for real cards.
        if parse_search_result_count(page):
            try:
                page.wait_for_timeout(1200)
            except Exception:
                pass
        if attempt >= 3 and page_has_no_jobs(page):
            return "empty"
        try:
            page.mouse.wheel(0, 1400)
        except Exception:
            pass
        pause_search(page)
    cards = locate_job_cards(page)
    try:
        if cards.count() > 0:
            return "ready"
    except Exception:
        pass
    if page_has_no_jobs(page):
        return "empty"
    # Result count without cards = still not ready (avoid hanging later).
    return "unknown"


def is_network_error(exc):
    msg = str(exc).lower()
    return any(marker in msg for marker in NETWORK_ERROR_MARKERS)


def is_offline(page):
    """True only when this PC cannot resolve the internet.

    navigator.onLine stays true during many DNS failures, so do not use it alone.
    """
    if machine_has_internet():
        return False
    try:
        return page.evaluate("navigator.onLine") is False
    except Exception:
        return not machine_has_internet()


def machine_has_internet(host="www.linkedin.com"):
    import socket

    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(5)
    try:
        socket.getaddrinfo(host, 443)
        return True
    except OSError:
        return False
    finally:
        socket.setdefaulttimeout(previous)


# Wait this long for internet before saving Excel and stopping the scrape.
OFFLINE_WAIT_SECONDS = 10 * 60


def wait_until_online(page, max_seconds=None):
    """Block until this PC can resolve the internet, or until timeout."""
    max_seconds = OFFLINE_WAIT_SECONDS if max_seconds is None else int(max_seconds)
    waited = 0
    print(
        f"  Waiting for internet (up to {max_seconds // 60} min {max_seconds % 60}s)…"
    )
    while waited < max_seconds:
        if stop_requested:
            return False
        if machine_has_internet():
            print("  Connection restored. Retrying...")
            return True
        try:
            page.wait_for_timeout(2000)
        except Exception:
            time.sleep(2)
        waited += 2
        if waited % 30 == 0:
            print(f"  ...still waiting for internet ({waited}s / {max_seconds}s)")
    return False


def handle_offline_outage(page, context_msg):
    """Wait up to 10 minutes for internet. On timeout: write Excel once and stop."""
    global stop_requested
    print(f"\n*** No internet — {context_msg} ***")
    if wait_until_online(page, OFFLINE_WAIT_SECONDS):
        return True

    print(
        "*** Still offline after 10 minutes — saving Excel and stopping scrape. ***",
        flush=True,
    )
    stop_requested = True
    progress["interrupted"] = True
    sync_checkpoint_context(progress)
    try:
        save_checkpoint(progress)
    except Exception:
        pass
    try:
        flush_active_save(force_excel=True)
    except Exception as exc:
        print(f"*** Excel save error after offline timeout: {exc} ***", flush=True)
    return False


def open_page_with_retry(page, url, context_msg, max_quick_retries=5):
    """Navigate with retries for transient network failures (connection reset, etc.)."""
    attempt = 0
    while True:
        if stop_requested:
            return False
        if not check_interrupt(page, context_msg):
            return False
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
            return True
        except Exception as exc:
            attempt += 1
            network = is_offline(page) or is_network_error(exc)
            if not network:
                print(f"  Load error: {exc}")
                return False

            print(f"  Network error ({context_msg}): {exc}")
            if machine_has_internet():
                if attempt <= max_quick_retries + 3:
                    wait_s = min(3 * attempt, 15)
                    print(
                        "  Your PC can reach the internet. LinkedIn failed to load in the "
                        f"browser ({type(exc).__name__}). Retrying in {wait_s}s "
                        f"(attempt {attempt})..."
                    )
                    try:
                        page.wait_for_timeout(wait_s * 1000)
                    except Exception:
                        time.sleep(wait_s)
                    continue
                print(
                    "  LinkedIn still will not open in the scraper browser, even though "
                    "this PC looks online. Stop and start the scrape again."
                )
                return False

            if attempt <= max_quick_retries:
                wait_s = min(2 * attempt, 12)
                print(f"  Retrying in {wait_s}s (attempt {attempt}/{max_quick_retries})...")
                try:
                    page.wait_for_timeout(wait_s * 1000)
                except Exception:
                    time.sleep(wait_s)
                continue

            if handle_offline_outage(page, context_msg):
                attempt = 0
                continue
            return False


def read_job_id_from_card(card):
    for attr in (
        "data-pm-job-id",
        "data-job-id",
        "data-occludable-job-id",
        "componentkey",
        "componentKey",
        "data-entity-urn",
    ):
        try:
            value = card.get_attribute(attr)
        except Exception:
            value = None
        if not value:
            continue
        digits = re.search(r"(\d{8,})", str(value))
        if digits:
            return digits.group(1)
        if str(value).isdigit():
            return str(value)

    for href_sel in (
        "a[href*='currentJobId=']",
        "a[href*='/jobs/view/']",
        "a[href*='/jobs/search-results/']",
    ):
        try:
            href = card.locator(href_sel).first.get_attribute("href")
        except Exception:
            href = None
        job_id = job_id_from_url(href)
        if job_id:
            return job_id

    try:
        href = card.get_attribute("href")
    except Exception:
        href = None
    return job_id_from_url(href)


def locate_job_cards(page):
    """Find job result cards using LinkedIn / AI LazyColumn selectors."""
    # Mark AI LazyColumn cards (SearchResultsMainContent) with a stable attribute.
    try:
        marked = page.evaluate(_MARK_AI_JOB_CARDS_JS)
        if marked:
            cards = page.locator('[data-pm-job-card="1"]')
            if cards.count() > 0:
                return cards
    except Exception:
        pass

    targets = [page]
    try:
        targets.extend(page.frames)
    except Exception:
        pass

    for target in targets:
        # Prefer marked AI cards inside frames too.
        try:
            target.evaluate(_MARK_AI_JOB_CARDS_JS)
            marked_cards = target.locator('[data-pm-job-card="1"]')
            if marked_cards.count() > 0:
                return marked_cards
        except Exception:
            pass

        for selector in JOB_CARD_SELECTORS:
            try:
                cards = target.locator(selector)
                count = cards.count()
                if count <= 0:
                    continue
                # Avoid matching giant page chrome wrappers.
                if count > 200:
                    continue
                return cards
            except Exception:
                continue

    try:
        cards = page.locator('[componentkey*="job-card"], [componentKey*="job-card"]')
        if cards.count() > 0:
            return cards
    except Exception:
        pass
    return page.locator(".job-card-container")


def mark_job_noticed(job_id, saved_job_ids):
    if job_id:
        saved_job_ids.add(job_id)


_COLLECT_VISIBLE_JOB_IDS_JS = """() => {
    const isDisabledJob = (el) => {
        if (!el) return false;
        let text = '';
        try { text = (el.innerText || '').toLowerCase(); } catch (e) { return false; }
        return (
            text.includes("won't recommend this job") ||
            text.includes("won\\u2019t recommend this job") ||
            text.includes('no longer accepting applications')
        );
    };

    const extractId = (href) => {
        if (!href) return null;
        let m = href.match(/[?&]currentJobId=(\\d{6,})/);
        if (m) return m[1];
        m = href.match(/\\/jobs\\/view\\/(\\d{6,})/);
        return m ? m[1] : null;
    };
    const ids = [];
    const seen = new Set();
    const add = (id) => {
        if (!id || seen.has(id)) return;
        seen.add(id);
        ids.push(id);
    };

    // Classic jobs list (visible in admin preview).
    document.querySelectorAll(
        '[data-occludable-job-id], [data-job-id], li.jobs-search-results__list-item, '
        + 'li.scaffold-layout__list-item, .job-card-container, [data-pm-job-id]'
    ).forEach((el) => {
        if (isDisabledJob(el)) return;
        const raw =
            el.getAttribute('data-occludable-job-id') ||
            el.getAttribute('data-job-id') ||
            el.getAttribute('data-pm-job-id') ||
            '';
        const m = String(raw).match(/(\\d{6,})/);
        if (m) add(m[1]);
        const a = el.querySelector
            ? el.querySelector('a[href*="currentJobId="], a[href*="/jobs/view/"]')
            : null;
        if (a) add(extractId(a.getAttribute('href') || ''));
    });

    // AI / classic anchors anywhere in main.
    const root = document.querySelector('main') || document.body;
    root.querySelectorAll('a[href*="currentJobId="], a[href*="/jobs/view/"]').forEach((a) => {
        const card = a.closest(
            'li, [data-occludable-job-id], [data-job-id], [data-pm-job-card], .job-card-container'
        ) || a.parentElement;
        if (isDisabledJob(card)) return;
        add(extractId(a.getAttribute('href') || ''));
    });

    // URL-selected job (always one).
    try {
        const urlId = extractId(location.href);
        if (urlId) add(urlId);
    } catch (e) {}
    return ids;
}"""

_SCROLL_JOB_LIST_JS = """() => {
    const candidates = [
        document.querySelector('.scaffold-layout__list'),
        document.querySelector('.scaffold-layout__list-container'),
        document.querySelector('ul.scaffold-layout__list'),
        document.querySelector('.jobs-search-results-list'),
        document.querySelector('[componentkey="SearchResultsMainContent"]'),
        document.querySelector('[data-component-type="LazyColumn"]'),
        document.querySelector('main'),
    ].filter(Boolean);
    let scrolled = false;
    for (const el of candidates) {
        let node = el;
        for (let i = 0; i < 8 && node; i++) {
            const style = window.getComputedStyle(node);
            const canScroll =
                (node.scrollHeight - node.clientHeight) > 40 &&
                /(auto|scroll|overlay)/.test(style.overflowY || '');
            if (canScroll) {
                node.scrollTop = Math.min(node.scrollTop + 900, node.scrollHeight);
                scrolled = true;
                break;
            }
            node = node.parentElement;
        }
        if (scrolled) break;
    }
    if (!scrolled) {
        window.scrollBy(0, 1200);
    }
    return true;
}"""


def collect_job_ids_from_results(page, max_rounds=18, target_count=40):
    """
    LinkedIn AI LazyColumn virtualizes cards — only a few exist in the DOM.
    Scroll the results list and collect unique currentJobId values.
    """
    ordered = []
    seen = set()
    stagnant = 0
    for round_idx in range(max_rounds):
        if stop_requested:
            break
        if not check_interrupt(page, "while collecting job ids"):
            break
        if round_idx == 0 or round_idx % 4 == 0:
            dismiss_job_search_overlays(page)
        try:
            page.evaluate(_MARK_AI_JOB_CARDS_JS)
        except Exception:
            pass
        try:
            batch = page.evaluate(_COLLECT_VISIBLE_JOB_IDS_JS) or []
        except Exception:
            batch = []
        added = 0
        for job_id in batch:
            jid = str(job_id or "").strip()
            if not jid or jid in seen:
                continue
            seen.add(jid)
            ordered.append(jid)
            added += 1
        if round_idx == 0 or added:
            print(f"  Job IDs collected: {len(ordered)}" + (f" (+{added})" if added else ""))
        if len(ordered) >= target_count:
            break
        if added == 0:
            stagnant += 1
            if stagnant >= 3 and ordered:
                break
        else:
            stagnant = 0
        try:
            page.evaluate(_SCROLL_JOB_LIST_JS)
        except Exception:
            try:
                page.mouse.wheel(0, 1400)
            except Exception:
                pass
        pause_search(page)
    return ordered


_DETAIL_PANE_JOB_ID_JS = """() => {
    const fromHref = (href) => {
        if (!href) return '';
        let m = href.match(/[?&]currentJobId=(\\d{6,})/);
        if (m) return m[1];
        m = href.match(/\\/jobs\\/view\\/(\\d{6,})/);
        return m ? m[1] : '';
    };
    const fromEl = (el) => {
        if (!el) return '';
        const raw =
            el.getAttribute('data-occludable-job-id') ||
            el.getAttribute('data-job-id') ||
            el.getAttribute('data-pm-job-id') ||
            '';
        const m = String(raw).match(/(\\d{6,})/);
        if (m) return m[1];
        const a = el.querySelector
            ? el.querySelector('a[href*="currentJobId="], a[href*="/jobs/view/"]')
            : null;
        return fromHref(a ? a.getAttribute('href') : '');
    };

    const activeSels = [
        'li.jobs-search-results-list__list-item--active',
        'li.scaffold-layout__list-item--active',
        'li.jobs-search-results__list-item--active',
        'li[aria-current="page"]',
        '.jobs-search-results-list__list-item--active',
    ];
    for (const sel of activeSels) {
        const el = document.querySelector(sel);
        const id = fromEl(el);
        if (id) return id;
    }

    const detailRoot =
        document.querySelector('.jobs-search__job-details--container') ||
        document.querySelector('.jobs-search__job-details') ||
        document.querySelector('div.scaffold-layout__detail') ||
        document.querySelector('.jobs-details');
    if (detailRoot) {
        const a = detailRoot.querySelector('a[href*="/jobs/view/"], a[href*="currentJobId="]');
        const id = fromHref(a ? a.getAttribute('href') : '');
        if (id) return id;
    }

    return '';
}"""

_CLICK_JOB_LIST_CARD_JS = """(id) => {
    const fromHref = (href) => {
        if (!href) return '';
        let m = href.match(/[?&]currentJobId=(\\d{6,})/);
        if (m) return m[1];
        m = href.match(/\\/jobs\\/view\\/(\\d{6,})/);
        return m ? m[1] : '';
    };
    const cardId = (el) => {
        if (!el) return '';
        const raw =
            el.getAttribute('data-occludable-job-id') ||
            el.getAttribute('data-job-id') ||
            el.getAttribute('data-pm-job-id') ||
            '';
        const m = String(raw).match(/(\\d{6,})/);
        if (m) return m[1];
        const a = el.querySelector('a[href*="currentJobId="], a[href*="/jobs/view/"]');
        return fromHref(a ? a.getAttribute('href') : '');
    };

    const listRoot =
        document.querySelector('.scaffold-layout__list') ||
        document.querySelector('.jobs-search-results-list') ||
        document.querySelector('main');
    const items = (listRoot || document).querySelectorAll(
        'li.scaffold-layout__list-item, li.jobs-search-results-list__list-item, '
        + 'li.jobs-search-results__list-item, [data-occludable-job-id], [data-pm-job-card]'
    );
    for (const item of items) {
        if (String(cardId(item)) !== String(id)) continue;
        try { item.scrollIntoView({ block: 'center', behavior: 'instant' }); } catch (e) {}
        const link = item.querySelector(
            'a[href*="currentJobId=' + id + '"], a[href*="/jobs/view/' + id + '"], '
            + '.job-card-list__title--link, .job-card-container__link, a'
        );
        const target = link || item;
        target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        if (typeof target.click === 'function') target.click();
        return true;
    }
    return false;
}"""


def detail_pane_job_id(page):
    try:
        return str(page.evaluate(_DETAIL_PANE_JOB_ID_JS) or "").strip()
    except Exception:
        return ""


def detail_pane_shows_id(page, job_id):
    job_id = str(job_id or "").strip()
    if not job_id:
        return False
    pane_id = detail_pane_job_id(page)
    return pane_id == job_id


def wait_for_detail_job_id(page, job_id, timeout_ms=12000):
    """Wait until the RIGHT detail pane / selected list card matches job_id."""
    job_id = str(job_id or "").strip()
    if not job_id:
        return False
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        if stop_requested:
            return False
        if detail_pane_shows_id(page, job_id):
            return True
        try:
            page.wait_for_timeout(350)
        except Exception:
            break
    return detail_pane_shows_id(page, job_id)


def job_page_shows_id(page, job_id):
    """True when the detail pane is showing this job (not merely listed in sidebar)."""
    return detail_pane_shows_id(page, job_id)


def _open_job_by_id_via_url(page, job_id):
    """Set currentJobId on the active search URL (classic + AI)."""
    try:
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

        parsed = urlparse(page.url)
        qs = parse_qs(parsed.query)
        qs["currentJobId"] = [str(job_id)]
        flat = []
        for key, values in qs.items():
            for val in values:
                flat.append((key, val))
        new_url = urlunparse(parsed._replace(query=urlencode(flat)))
        if not open_page_with_retry(page, new_url, f"opening job {job_id}"):
            return False
        page.wait_for_timeout(700)
        return wait_for_detail_job_id(page, job_id, timeout_ms=8000)
    except Exception:
        return False


def open_job_by_id(page, job_id):
    """Open a job in the search-results detail pane by currentJobId."""
    job_id = str(job_id or "").strip()
    if not job_id:
        return False

    if detail_pane_shows_id(page, job_id):
        return True

    clicked = False
    try:
        clicked = bool(page.evaluate(_CLICK_JOB_LIST_CARD_JS, job_id))
    except Exception:
        clicked = False

    if not clicked:
        try:
            clicked = bool(
                page.evaluate(
                    """(id) => {
                        const el = document.querySelector(
                            '[data-occludable-job-id="' + id + '"], [data-job-id="' + id + '"]'
                        );
                        if (!el) return false;
                        try { el.scrollIntoView({ block: 'center' }); } catch (e) {}
                        (el.querySelector('a') || el).click();
                        return true;
                    }""",
                    job_id,
                )
            )
        except Exception:
            clicked = False

    if clicked and wait_for_detail_job_id(page, job_id, timeout_ms=6000):
        return True

    # Playwright click fallback (more reliable on classic split-view UI).
    try:
        card = page.locator(
            f'[data-occludable-job-id="{job_id}"], [data-job-id="{job_id}"], '
            f'[data-pm-job-id="{job_id}"]'
        ).first
        if card.count() > 0:
            card.scroll_into_view_if_needed(timeout=3000)
            card.click(timeout=4000)
            if wait_for_detail_job_id(page, job_id, timeout_ms=6000):
                return True
    except Exception:
        pass

    if _open_job_by_id_via_url(page, job_id):
        return wait_for_detail_job_id(page, job_id, timeout_ms=8000)

    return detail_pane_shows_id(page, job_id)


def resolve_opened_job_id(page, requested_job_id, apply_link=""):
    """
    Prefer the job id from the results list.

    LinkedIn often leaves a stale currentJobId in the search URL after clicking
    another card, which caused every job to look like the same id.
    """
    requested_job_id = str(requested_job_id or "").strip()
    url_job_id = str(job_id_from_url(apply_link or "") or "").strip()
    if not requested_job_id:
        return url_job_id
    if url_job_id and url_job_id == requested_job_id:
        return requested_job_id
    if job_page_shows_id(page, requested_job_id):
        return requested_job_id
    if url_job_id and url_job_id != requested_job_id:
        print(
            f"  Note: URL shows job {url_job_id} but list id is {requested_job_id} "
            f"— using list id."
        )
    return requested_job_id


def card_keyword_reject_early(keyword, card_text, strict_title=False):
    """Do not reject list cards on keyword alone — open detail and use experience filter."""
    return False, ""


def scrape_job_by_id(
    page,
    job_id,
    seen_apply_urls,
    saved_job_ids,
    keyword="",
    strict_title=True,
    index=0,
    already_open=False,
):
    """Open one job by ID, read full description, apply senior/fresher filters."""
    job_id = str(job_id or "").strip()
    if not job_id:
        return None

    if not already_open:
        print(f"  Opening job {index + 1} ({job_id})...")
        pause_search(page)
        dismiss_job_search_overlays(page)
        if not open_job_by_id(page, job_id):
            print(f"  Could not open job {job_id} — continuing.")
            return None
        pause_search(page)

    detail_ok = wait_for_job_detail(page, job_id=job_id, timeout_ms=12000)
    if not detail_ok:
        if is_offline(page):
            raise RuntimeError("offline while opening job detail")
        pane_id = detail_pane_job_id(page)
        print(
            f"  Detail pane did not switch to job {job_id} "
            f"(pane shows {pane_id or 'unknown'}) — skipping."
        )
        return None

    try:
        for sel in (
            'button:has-text("Show more")',
            'button[aria-label*="Show more" i]',
            ".jobs-description__footer-button",
            "button.jobs-description__footer-button",
        ):
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible():
                btn.click(timeout=2000)
                page.wait_for_timeout(400)
                break
    except Exception:
        pass

    pause_search(page)
    apply_link = page.url
    opened_job_id = resolve_opened_job_id(page, job_id, apply_link)
    if not detail_pane_shows_id(page, job_id):
        pane_id = detail_pane_job_id(page)
        print(
            f"  Stale detail pane for job {job_id} (showing {pane_id or 'unknown'}) — skipping."
        )
        return None

    page_text = extract_job_panel_text(page, max_chars=20000)
    if is_disabled_job_text(page_text):
        print(f"  Skipping hidden/disabled job ({job_id}) — LinkedIn won't recommend it.")
        mark_job_noticed(opened_job_id, saved_job_ids)
        return None

    dom_fields = extract_job_fields_from_dom(page)
    if len(page_text) < 40 and not (dom_fields.get("title") and dom_fields.get("company")):
        print(f"  Empty job detail for {job_id} — continuing.")
        mark_job_noticed(opened_job_id, saved_job_ids)
        return None

    canonical = f"https://www.linkedin.com/jobs/view/{opened_job_id}/"
    raw_job = parse_job_detail(page_text, apply_link=canonical)
    # Prefer DOM title/company/description — text parsing often grabs section headers.
    if dom_fields.get("title"):
        raw_job["job_title"] = dom_fields["title"]
    if dom_fields.get("company"):
        raw_job["company_name"] = dom_fields["company"]
    if dom_fields.get("description"):
        raw_job["description_text"] = dom_fields["description"]
        if not raw_job.get("experience_raw"):
            from job.job_scraper import extract_experience_raw

            raw_job["experience_raw"] = extract_experience_raw(dom_fields["description"])

    if not has_title_and_company(raw_job):
        try:
            page.wait_for_timeout(900)
        except Exception:
            pass
        page_text = extract_job_panel_text(page, max_chars=20000)
        dom_fields = extract_job_fields_from_dom(page)
        raw_job = parse_job_detail(page_text, apply_link=canonical)
        if dom_fields.get("title"):
            raw_job["job_title"] = dom_fields["title"]
        if dom_fields.get("company"):
            raw_job["company_name"] = dom_fields["company"]
        if dom_fields.get("description"):
            raw_job["description_text"] = dom_fields["description"]
    if not has_title_and_company(raw_job):
        print(f"  Could not parse title/company ({job_id}) — continuing.")
        mark_job_noticed(opened_job_id, saved_job_ids)
        return None

    print(f"  Checking: {raw_job.get('job_title', '')[:70]} (id {job_id})")

    if is_senior_title(raw_job.get("job_title", "")):
        print(f"  Skipping senior-level role: {raw_job.get('job_title', '')[:60]}")
        mark_job_noticed(opened_job_id, saved_job_ids)
        return None

    if is_stale_job_card(
        f"{raw_job.get('posted_raw', '')}\n{page_text[:500]}", MAX_JOB_AGE_HOURS
    ):
        print(
            f"  Skipping job older than {MAX_JOB_AGE_HOURS}h: "
            f"{raw_job.get('job_title', '')[:60]}"
        )
        mark_job_noticed(opened_job_id, saved_job_ids)
        return None

    scrape_mode = "job"
    skills = []
    target_exp = ""
    min_skills_match = 1
    try:
        from job import config as _cfg

        scrape_mode = (getattr(_cfg, "SCRAPE_MODE", None) or SCRAPE_MODE or "job").strip().lower()
        skills = list(getattr(_cfg, "PERFECT_MATCH_SKILLS", None) or PERFECT_MATCH_SKILLS or [])
        target_exp = (
            getattr(_cfg, "PERFECT_MATCH_EXPERIENCE", None) or PERFECT_MATCH_EXPERIENCE or ""
        )
        min_skills_match = int(
            getattr(_cfg, "PERFECT_MATCH_MIN_SKILLS", None) or PERFECT_MATCH_MIN_SKILLS or 1
        )
    except Exception:
        scrape_mode = (SCRAPE_MODE or "job").strip().lower()
        skills = list(PERFECT_MATCH_SKILLS or [])
        target_exp = PERFECT_MATCH_EXPERIENCE or ""
        min_skills_match = int(PERFECT_MATCH_MIN_SKILLS or 1)

    if scrape_mode == "perfect_match":
        # Keep/skip based on description skill count + experience — not single-skill keyword match.
        skip, skip_reason = should_skip_for_perfect_match(
            skills=skills,
            target_experience=target_exp,
            job_title=raw_job.get("job_title", ""),
            description_text=raw_job.get("description_text", ""),
            experience_raw=raw_job.get("experience_raw", ""),
            min_skills_match=min_skills_match,
        )
        if skip:
            print(f"  Skipping ({skip_reason}): {raw_job.get('job_title', '')[:60]}")
            mark_job_noticed(opened_job_id, saved_job_ids)
            return None
        from job.job_filter import job_matches_skills

        _ok, _reason, matched_n = job_matches_skills(
            skills,
            job_title=raw_job.get("job_title", ""),
            description_text=raw_job.get("description_text", ""),
            min_match=min_skills_match,
        )
        print(
            f"  Skill match OK ({matched_n}/{len(skills)}, need {min_skills_match}): "
            f"{raw_job.get('job_title', '')[:60]}"
        )
    else:
        skip_kw, kw_reason = should_skip_for_keyword_mismatch(
            keyword,
            job_title=raw_job.get("job_title", ""),
            description_text=raw_job.get("description_text", ""),
            experience_raw=raw_job.get("experience_raw", ""),
            strict_title=strict_title,
            allow_experience_bypass=True,
        )
        if skip_kw:
            print(f"  Skipping ({kw_reason}): {raw_job.get('job_title', '')[:60]}")
            mark_job_noticed(opened_job_id, saved_job_ids)
            return None
        if kw_reason == "keyword optional (experience filter applies)":
            print(
                f"  Keyword optional (experience filter applies): "
                f"{raw_job.get('job_title', '')[:60]}"
            )

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
    seen_apply_urls.add(str(opened_job_id))
    return job


def scrape_job_card(
    page, cards, index, seen_apply_urls, saved_job_ids, keyword="", strict_title=True
):
    card = cards.nth(index)
    card_job_id = read_job_id_from_card(card)
    if card_job_id:
        return scrape_job_by_id(
            page,
            card_job_id,
            seen_apply_urls,
            saved_job_ids,
            keyword=keyword,
            strict_title=strict_title,
            index=index,
        )

    try:
        card_text = card.inner_text(timeout=5000)
    except Exception:
        card_text = ""

    if is_disabled_job_text(card_text):
        print(f"  Skipping hidden/disabled job (card {index + 1}).")
        if card_job_id:
            mark_job_noticed(card_job_id, saved_job_ids)
        return None

    title_hint = _card_title_from_card_text(card_text)
    if is_senior_title(title_hint) or is_senior_title(card_text.split("\n", 1)[0]):
        print(f"  Skipping senior-level role (card {index + 1}): {title_hint[:60]}")
        return None
    if is_stale_job_card(card_text, MAX_JOB_AGE_HOURS):
        print(
            f"  Skipping job older than {MAX_JOB_AGE_HOURS}h (card {index + 1})."
        )
        return None

    # Do not hard-reject on sparse card chrome — open detail first.
    skip_kw, kw_reason = card_keyword_reject_early(
        keyword, card_text, strict_title=strict_title
    )
    if skip_kw:
        print(f"  Skipping ({kw_reason}) (card {index + 1}).")
        return None

    print(f"  Opening job {index + 1}...")
    pause_search(page)
    if not open_job_card(page, card, job_id=""):
        print(f"  Could not open card {index + 1} — continuing.")
        return None
    pause_search(page)

    opened_job_id = job_id_from_url(page.url) or ""
    if opened_job_id:
        return scrape_job_by_id(
            page,
            opened_job_id,
            seen_apply_urls,
            saved_job_ids,
            keyword=keyword,
            strict_title=strict_title,
            index=index,
            already_open=True,
        )
    return None


def _card_title_from_card_text(card_text):
    """First meaningful line(s) from a job card for senior/title checks."""
    lines = []
    for raw in (card_text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if lower in {"promoted", "viewed", "easy apply", "actively reviewing applicants"}:
            continue
        if lower.startswith("be an early applicant"):
            continue
        if re.fullmatch(r"\d+\s*(second|minute|hour|day|week|month)s?\s*ago", lower):
            continue
        lines.append(line)
        if len(lines) >= 2:
            break
    return " ".join(lines)


def scrape_results_page(
    page, seen_apply_urls, saved_job_ids, start_card=0, keyword="", strict_title=True
):
    global stop_requested, jobs_collected, progress

    pause_search(page)
    hit_recommended = False

    # AI LazyColumn only keeps a few cards in the DOM — collect IDs while scrolling.
    print("  Collecting job IDs from LinkedIn results list...")
    job_ids = collect_job_ids_from_results(
        page,
        max_rounds=20,
        target_count=min(RESULTS_PER_PAGE, 40) if RESULTS_PER_PAGE else 40,
    )
    if start_card:
        job_ids = job_ids[start_card:]

    card_count = len(job_ids)
    known_on_page = sum(1 for jid in job_ids if jid in saved_job_ids)
    print(
        f"  Jobs to check on this page: {card_count} "
        f"({known_on_page} already noticed, {card_count - known_on_page} to open)"
    )

    if card_count == 0:
        # Fallback to old locator path if ID harvest failed.
        try:
            cards = locate_job_cards(page)
            card_count = min(cards.count(), 25)
        except Exception:
            cards = None
            card_count = 0
        if card_count <= 0:
            return [], 0, 0, False, False
        print(f"  Fallback card locator found {card_count} node(s).")
        page_jobs = []
        for index in range(card_count):
            if not check_interrupt(page, f"while reading fallback card {index + 1}"):
                break
            try:
                job = scrape_job_card(
                    page,
                    cards,
                    index,
                    seen_apply_urls,
                    saved_job_ids,
                    keyword=keyword,
                    strict_title=strict_title,
                )
            except Exception as exc:
                print(f"  ERROR on card {index + 1} (continuing): {exc}")
                continue
            if job is not None:
                page_jobs.append(job)
                jobs_collected += 1
                print(
                    f"  {job['job_role']} | {job['company_name']} | "
                    f"{job['posted_text']} | {job['freshers_eligible']}"
                )
                if MAX_JOBS and jobs_collected >= MAX_JOBS:
                    stop_requested = True
                    break
        progress["card_index"] = 0
        return page_jobs, card_count, 0, False, False

    page_jobs = []
    stale_age_on_page = 0
    index = 0
    while index < card_count:
        progress["card_index"] = index
        sync_checkpoint_context(progress)
        save_checkpoint(progress)

        if not check_interrupt(
            page,
            f"while reading job {index + 1} of {card_count} on this page",
        ):
            break

        job_id = job_ids[index]
        try:
            job = scrape_job_by_id(
                page,
                job_id,
                seen_apply_urls,
                saved_job_ids,
                keyword=keyword,
                strict_title=strict_title,
                index=index,
            )
        except Exception as exc:
            if is_offline(page) or is_network_error(exc):
                if handle_offline_outage(
                    page,
                    f"job {index + 1} of {card_count} on this page",
                ):
                    continue
                print(f"  Network error on job {index + 1} — stopping after offline wait.")
                break
            print(f"  ERROR on job {index + 1} (continuing): {exc}")
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
    all_stale_age = False
    return page_jobs, card_count, known_on_page, all_stale_age, hit_recommended


def format_location_query(location):
    text = (location or "").strip()
    return text.title() if text else ""


def build_linkedin_keywords_query(keyword):
    """
    Build LinkedIn keywords query.

    Fresher/junior words (fresher, entry, graduate…) are dropped — Entry level is
    applied via f_E=2 / Experience level filter instead of the search box.
    """
    text = (keyword or "").strip()
    if not text:
        return text
    terms = keyword_match_terms(text)
    if not terms:
        return text
    if KEYWORD_MATCH_MODE == "max":
        # Unquoted = broader LinkedIn/AI recall.
        return " ".join(terms)
    if len(terms) == 1:
        return terms[0]
    return f'"{" ".join(terms)}"'


def build_job_search_results_url(keywords_query, location, time_filter, start=0):
    """
    Build LinkedIn AI job search URL (/jobs/search-results/).

    Matches current LinkedIn shape, e.g.:
    /jobs/search-results/?keywords=python%20developer&geoId=114806696
      &distance=100.0&f_TPR=r86400&sortBy=R&origin=JOBS_HOME_KEYWORD_HISTORY
    """
    params = [
        f"keywords={quote(keywords_query or '')}",
        f"f_TPR={time_filter}",
        f"f_E={LINKEDIN_ENTRY_LEVEL_F_E}",
        f"sortBy={JOB_SEARCH_SORT_BY}",
        "origin=JOBS_HOME_KEYWORD_HISTORY",
        f"start={int(start or 0)}",
    ]
    geo_id = resolve_job_geo_id(location)
    location_query = format_location_query(location)
    if geo_id:
        params.append(f"geoId={geo_id}")
    if location_query:
        params.append(f"location={quote(location_query)}")
    # Always request 100 km around the location when a place is set.
    if geo_id or location_query:
        params.append(f"distance={float(JOB_SEARCH_DISTANCE_KM)}")
    return "https://www.linkedin.com/jobs/search-results/?" + "&".join(params)


def build_classic_job_search_url(keywords_query, location, time_filter, start=0):
    """Classic LinkedIn jobs search URL — f_E filters are reliable here."""
    params = [
        f"keywords={quote(keywords_query or '')}",
        f"f_TPR={time_filter}",
        f"f_E={LINKEDIN_ENTRY_LEVEL_F_E}",
        f"start={int(start or 0)}",
        f"sortBy={JOB_SEARCH_SORT_BY}",
    ]
    geo_id = resolve_job_geo_id(location)
    location_query = format_location_query(location)
    if geo_id:
        params.append(f"geoId={geo_id}")
    if location_query:
        params.append(f"location={quote(location_query)}")
    if geo_id or location_query:
        params.append(f"distance={float(JOB_SEARCH_DISTANCE_KM)}")
    return "https://www.linkedin.com/jobs/search/?" + "&".join(params)


def scrape_keyword_search(page, keyword, location, saved_job_ids, start_page=0, on_batch_saved=None):
    print(f"\nSearching: {keyword} | {location} ({job_age_label(MAX_JOB_AGE_HOURS)})")
    terms = keyword_match_terms(keyword)
    if terms:
        print(
            f"  Keyword filter mode={KEYWORD_MATCH_MODE}: "
            f"require skill terms from [{', '.join(terms)}] "
            f"(role-only titles like 'Java Developer' are skipped for python searches)"
            if any(t not in {"developer", "engineer", "programmer", "analyst", "consultant", "associate", "specialist"} for t in terms)
            else f"Keyword filter mode={KEYWORD_MATCH_MODE}: keep jobs matching any of [{', '.join(terms)}]"
        )
    scraped_jobs = []
    seen_apply_urls = set()
    time_filter = linkedin_time_filter_param(MAX_JOB_AGE_HOURS)
    location_query = format_location_query(location)
    keywords_query = build_linkedin_keywords_query(keyword)
    geo_id = resolve_job_geo_id(location)
    print(f"  LinkedIn query: {keywords_query}")
    print(
        f"  LinkedIn filters: Past 24 hours + Entry level + "
        f"Most relevant + {JOB_SEARCH_DISTANCE_KM} km radius"
    )
    if geo_id:
        print(f"  Job geoId: {geo_id} ({location_query or location})")
    else:
        print(f"  No job geoId map for '{location}' — using location text only.")
    total_results = None
    empty_pages = 0

    for page_num in range(start_page, MAX_PAGES):
        progress["page_num"] = page_num
        sync_checkpoint_context(progress)
        save_checkpoint(progress)

        if not check_interrupt(page, f"before page {page_num + 1} of {keyword} | {location}"):
            print("  Stop requested. Halting pagination.")
            break

        start = page_num * RESULTS_PER_PAGE
        if total_results is not None and start >= total_results:
            print(
                f"  Reached end of search results "
                f"({total_results} listed)."
            )
            break

        search_url = build_classic_job_search_url(
            keywords_query, location, time_filter, start=start
        )
        print(f"  Page {page_num + 1} (start={start})")
        print(f"  URL: {search_url}")

        try:
            if not open_page_with_retry(page, search_url, f"loading page {page_num + 1}"):
                if stop_requested:
                    print("  Stop requested. Halting pagination.")
                    break
                print("  SKIP (page load failed) — continuing to next page.")
                empty_pages += 1
                if empty_pages >= 3:
                    print("  Too many empty/failed pages — moving to next search.")
                    break
                continue

            pause_search(page)
            prepare_job_results_page(page)
            print("  Using LinkedIn job list (MAX keyword filter — keep more jobs).")

            load_state = wait_for_job_results(page)
            if load_state == "interrupted":
                print("  Stop requested. Halting pagination.")
                break
            if load_state == "empty":
                print("  No matching jobs listed — trying next page/search.")
                empty_pages += 1
                if empty_pages >= 2:
                    break
                continue
            if load_state == "recommended":
                # Do not abort the whole keyword; try scraping whatever cards exist.
                print(
                    "  Recommended chrome detected — still scraping visible cards."
                )
            if load_state == "unknown":
                print("  Job cards slow to load — retrying this page once...")
                diagnose_missing_job_cards(page)
                try:
                    page.reload(wait_until="domcontentloaded", timeout=60000)
                except Exception:
                    pass
                pause_search(page)
                prepare_job_results_page(page)
                load_state = wait_for_job_results(page, max_attempts=12)
                if load_state in ("unknown", "empty"):
                    print("  Job cards did not load — continuing to next page.")
                    empty_pages += 1
                    if empty_pages >= 3:
                        break
                    continue
                if load_state == "interrupted":
                    print("  Stop requested. Halting pagination.")
                    break

            ensure_entry_level_experience_filter(
                page,
                keywords_query=keywords_query,
                location=location,
                time_filter=time_filter,
                start=start,
            )
            ensure_search_sort_and_distance(
                page,
                keywords_query=keywords_query,
                location=location,
                time_filter=time_filter,
                start=start,
            )
            dismiss_job_search_overlays(page)

            if total_results is None:
                total_results = parse_search_result_count(page)
                if total_results is not None:
                    print(f"  LinkedIn reports ~{total_results} result(s) for this search.")
                    if start >= total_results:
                        print("  Past listed result count — moving on.")
                        break

            try:
                if page_shows_similar_not_exact(page):
                    print(
                        "  LinkedIn AI showing similar jobs — MAX filter will still keep "
                        "cards that match any keyword term."
                    )
            except Exception as exc:
                print(f"  Similar-jobs check skipped ({exc}).")

            print("  Scanning job cards on this page...")
            # Never hard-stop here on recommended markers; scrape cards first.
            start_card = progress.get("card_index", 0) if page_num == start_page else 0
            try:
                (
                    page_jobs,
                    card_count,
                    known_on_page,
                    all_stale_age,
                    hit_recommended,
                ) = scrape_results_page(
                    page,
                    seen_apply_urls,
                    saved_job_ids,
                    start_card=start_card,
                    keyword=keyword,
                    strict_title=False,
                )
            except Exception as exc:
                import traceback

                print(f"  Page scrape error (continuing): {exc}")
                print(traceback.format_exc())
                empty_pages += 1
                if empty_pages >= 3:
                    print("  Too many page errors — moving to next search.")
                    break
                continue

            if card_count <= 0:
                print("  No job cards found on this page — continuing.")
                diagnose_missing_job_cards(page)
                empty_pages += 1
                if empty_pages >= 3:
                    break
                continue

            for j in page_jobs:
                try:
                    j["keyword"] = keyword
                except Exception:
                    pass
            scraped_jobs.extend(page_jobs)

            if page_jobs:
                empty_pages = 0
            else:
                empty_pages += 1

            if all_stale_age:
                print("  Job age filter reached — moving to next search.")
                break

            if card_count == 0:
                print("  No cards on this page — continuing to next page.")
                if empty_pages >= 3:
                    print("  Too many empty pages — moving to next search.")
                    break
                continue

            if page_jobs:
                print(
                    f"  Found {len(page_jobs)} keyword-matched job(s) on page {page_num + 1}."
                )
                if on_batch_saved:
                    try:
                        on_batch_saved(page_jobs)
                    except Exception as exc:
                        print(f"  Save batch warning (continuing): {exc}")
            elif known_on_page == card_count:
                print(
                    f"  Page {page_num + 1}: all {known_on_page} card(s) already noticed — "
                    "continuing to next page."
                )
            else:
                print(
                    f"  Page {page_num + 1}: 0 jobs saved after experience filter "
                    f"({card_count} card(s) checked) — continuing to next page."
                )

            # Only stop when recommended clearly replaced the list.
            if hit_recommended and card_count <= 2 and recommended_section_dominates(page):
                print(
                    "  Search list replaced by Top recommended — moving to next search."
                )
                break

            if total_results is not None and (start + max(card_count, 1)) >= total_results:
                print(
                    f"  Covered listed results (~{total_results})."
                )
                break

            pause_search(page)
        except Exception as exc:
            import traceback

            print(f"  Search page error (continuing): {exc}")
            print(traceback.format_exc())
            empty_pages += 1
            if empty_pages >= 3:
                print("  Too many errors — moving to next search.")
                break
            continue

    progress["page_num"] = 0
    progress["card_index"] = 0
    print(f"  Total jobs collected: {len(scraped_jobs)} across pages")
    return scraped_jobs


def is_logged_in(page):
    return check_session_on_job_search(page)


def save_progress(jobs_this_run, today_store, write_excel=False):
    """Merge jobs into today's JSON.

    Excel is written only on: scrape complete, explicit Stop, low-battery shutdown,
    or offline for 10 minutes — never after each search/location.
    """
    new_jobs = sort_jobs_newest_first(deduplicate_jobs(jobs_this_run))
    all_today_jobs = deduplicate_jobs(new_jobs + today_store["jobs"])
    today_store["jobs"] = all_today_jobs
    save_today_store(today_store)

    if not write_excel or not all_today_jobs:
        if new_jobs:
            print(
                f"  Checkpoint: {len(new_jobs)} new job(s) "
                f"({len(all_today_jobs)} total today). "
                "Excel is written only on finish / Stop / shutdown / 10-min offline."
            )
        return len(new_jobs), len(all_today_jobs)

    excel_path = daily_excel_path()
    try:
        row_count = write_branded_excel(all_today_jobs, excel_path)
        print(
            f"\nExcel saved: {excel_path} — {len(all_today_jobs)} job(s) today "
            f"({row_count} shown after filters)."
        )
    except Exception as exc:
        from common.file_errors import friendly_file_error

        if isinstance(exc, OSError):
            detail = friendly_file_error(exc, excel_path, "write")
        else:
            detail = f"Could not write Excel ({exc})"
        try:
            print(f"\n*** {detail} ***")
            print(
                "  Today's JSON backup was saved. Close the Excel file and run again to refresh it."
            )
        except Exception:
            pass
    return len(new_jobs), len(all_today_jobs)


def refresh_runtime_search_config():
    """Re-bind search lists from job.config after Django UI overrides."""
    global JOB_KEYWORDS, LOCATIONS, MAX_JOB_AGE_HOURS, MAX_JOBS, MAX_PAGES
    global SEARCH_MAX_DELAY, SEARCH_MIN_DELAY, RESULTS_PER_PAGE
    global SKIP_SEARCHES, SKIP_PREVIOUS_JOBS, SCRAPE_MODE
    global PERFECT_MATCH_SKILLS, PERFECT_MATCH_EXPERIENCE, PERFECT_MATCH_MIN_SKILLS
    global JOB_SEARCH_DISTANCE_KM, JOB_SEARCH_SORT_BY
    import job.config as cfg

    JOB_KEYWORDS = list(getattr(cfg, "JOB_KEYWORDS", None) or [])
    LOCATIONS = list(getattr(cfg, "LOCATIONS", None) or [])
    MAX_JOB_AGE_HOURS = getattr(cfg, "MAX_JOB_AGE_HOURS", MAX_JOB_AGE_HOURS)
    MAX_JOBS = getattr(cfg, "MAX_JOBS", MAX_JOBS)
    MAX_PAGES = getattr(cfg, "MAX_PAGES", MAX_PAGES)
    SEARCH_MAX_DELAY = getattr(cfg, "SEARCH_MAX_DELAY", SEARCH_MAX_DELAY)
    SEARCH_MIN_DELAY = getattr(cfg, "SEARCH_MIN_DELAY", SEARCH_MIN_DELAY)
    RESULTS_PER_PAGE = getattr(cfg, "RESULTS_PER_PAGE", RESULTS_PER_PAGE)
    SKIP_SEARCHES = list(getattr(cfg, "SKIP_SEARCHES", None) or [])
    SKIP_PREVIOUS_JOBS = bool(getattr(cfg, "SKIP_PREVIOUS_JOBS", False))
    SCRAPE_MODE = (getattr(cfg, "SCRAPE_MODE", "job") or "job").strip().lower()
    PERFECT_MATCH_SKILLS = list(getattr(cfg, "PERFECT_MATCH_SKILLS", None) or [])
    PERFECT_MATCH_EXPERIENCE = str(getattr(cfg, "PERFECT_MATCH_EXPERIENCE", "") or "")
    try:
        PERFECT_MATCH_MIN_SKILLS = max(1, int(getattr(cfg, "PERFECT_MATCH_MIN_SKILLS", 1) or 1))
    except (TypeError, ValueError):
        PERFECT_MATCH_MIN_SKILLS = 1
    try:
        JOB_SEARCH_DISTANCE_KM = int(getattr(cfg, "JOB_SEARCH_DISTANCE_KM", JOB_SEARCH_DISTANCE_KM) or 100)
    except (TypeError, ValueError):
        JOB_SEARCH_DISTANCE_KM = 100
    JOB_SEARCH_SORT_BY = str(getattr(cfg, "JOB_SEARCH_SORT_BY", JOB_SEARCH_SORT_BY) or "R")
    return JOB_KEYWORDS, LOCATIONS


def resolve_start_progress(allow_resume=True):
    global progress
    today = date.today().strftime("%Y-%m-%d")
    checkpoint = load_checkpoint()
    refresh_runtime_search_config()
    plan = search_plan_signature(JOB_KEYWORDS, LOCATIONS)

    if checkpoint.get("interrupted") and checkpoint.get("date") == today:
        context = checkpoint.get("context") or checkpoint_context(checkpoint)
        if (
            not allow_resume
            or (checkpoint.get("search_plan") and checkpoint.get("search_plan") != plan)
        ):
            if allow_resume:
                print("\nKeyword/location list changed since the last run.")
            print("Starting a fresh scrape (previous checkpoint cleared).")
            clear_checkpoint()
            progress = default_checkpoint()
            return "fresh"
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


def run(allow_resume=True):
    global stop_requested, progress
    refresh_runtime_search_config()
    start_mode = resolve_start_progress(allow_resume=allow_resume)
    if start_mode == "exit":
        return
    resuming = start_mode == "resume"
    refresh_runtime_search_config()

    with launch_browser(blocked_resource_types={"image", "media", "font"}) as (
        browser,
        context,
        page,
    ):
        print("Opening LinkedIn Jobs...")
        if not open_page_with_retry(page, "https://www.linkedin.com/jobs/", "opening LinkedIn Jobs"):
            print("\n*** Could not open LinkedIn Jobs (network error). ***")
            print("Check your internet connection and try again.")
            raise SystemExit(1)
        pause_search(page)
        dismiss_job_search_overlays(page)

        if not is_logged_in(page):
            print("\n*** LinkedIn session expired! ***")
            print("Run: python common/save_session.py")
            print("Then: python job/job.py")
            raise SystemExit(1)

        today_store = load_today_store()
        saved_job_ids = set()
        previous_day_count = count_previous_daily_files()
        already_saved_today = len(job_ids_from_jobs(today_store["jobs"]))
        excel_path = daily_excel_path()
        print(
            f"Daily JSON backup loaded ({already_saved_today} job(s) so far today). "
            f"Excel ({excel_path}) is written only when: scrape finishes, Stop, "
            f"low-battery shutdown, or offline for 10 minutes "
            f"({previous_day_count} previous day file(s))."
        )
        previous_summary = summarize_known_jobs()
        if previous_summary:
            print("Previous daily files:")
            for day_label, job_count in previous_summary:
                print(f"  - {day_label}: {job_count} job(s)")
        if SKIP_PREVIOUS_JOBS:
            known = len(known_job_ids())
            print(
                f"Skip previous jobs is on ({known} known id(s)) — "
                "all jobs on each page are still opened and checked; "
                "duplicates are deduped when saving."
            )
        else:
            print("Skip previous jobs is off — all jobs will be checked (duplicates deduped on save).")
        print("Scraping searches one by one; jobs are saved to JSON until you stop.")
        active_searches = sum(
            1
            for kw in JOB_KEYWORDS
            for loc in LOCATIONS
            if not is_search_skipped(kw, loc, current_skip_searches())
        )
        print(
            f"Search plan: {len(JOB_KEYWORDS)} keyword(s) × {len(LOCATIONS)} location(s) "
            f"= {active_searches} active search(es)."
        )
        for kw in JOB_KEYWORDS:
            for loc in LOCATIONS:
                label = f"{kw} | {loc or 'anywhere'}"
                if is_search_skipped(kw, loc, current_skip_searches()):
                    print(f"  - {label} (unchecked — will skip)")
                else:
                    print(f"  - {label}")
        if resuming:
            print(f"Resume point: {checkpoint_context(progress)}")

        jobs_this_run = []
        pending_jobs = jobs_this_run
        _register_save_context(pending_jobs, today_store)
        _start_stop_watcher()
        _start_battery_watcher()
        try:
            from common.battery_guard import (
                format_status,
                get_battery_status,
                get_critical_percent,
                set_critical_percent,
            )

            set_critical_percent(get_critical_percent())
            threshold = get_critical_percent()
            print(
                f"Battery guard on: save Excel + shutdown if below {threshold}% and unplugged "
                f"(now: {format_status(get_battery_status())})."
            )
        except Exception:
            print("Battery guard on: save Excel + shutdown if below threshold and unplugged.")
        keyword_start, location_start, page_start = normalize_resume_indices(progress)

        def persist_job_batch(batch):
            if not batch:
                return
            pending_jobs.extend(batch)
            save_progress(pending_jobs, today_store)
            pending_jobs.clear()

        if (
            progress.get("keyword_index", 0) != keyword_start
            or progress.get("location_index", 0) != location_start
        ):
            print("Adjusted resume point to match the current keyword/location list.")
            progress["keyword_index"] = keyword_start
            progress["location_index"] = location_start
            progress["page_num"] = page_start
            progress["card_index"] = 0
            progress["search_plan"] = search_plan_signature()
            sync_checkpoint_context(progress)
            save_checkpoint(progress)

        try:
            for keyword_index, keyword in enumerate(JOB_KEYWORDS):
                if keyword_index < keyword_start:
                    continue
                progress["keyword_index"] = keyword_index
                progress["search_plan"] = search_plan_signature()
                sync_checkpoint_context(progress)
                save_checkpoint(progress)

                if not check_interrupt(page, f"before keyword {keyword}"):
                    break

                location_from = location_start if keyword_index == keyword_start else 0
                for location_index, location in enumerate(LOCATIONS):
                    if location_index < location_from:
                        continue
                    if is_search_skipped(keyword, location, current_skip_searches()):
                        print(f"Skipping search (unchecked): {keyword} | {location}")
                        continue
                    progress["location_index"] = location_index
                    progress["search_plan"] = search_plan_signature()
                    sync_checkpoint_context(progress)
                    save_checkpoint(progress)

                    if not check_interrupt(page, f"before location {location}"):
                        break

                    start_page = page_start if (
                        keyword_index == keyword_start
                        and location_index == location_start
                    ) else 0
                    network_attempts = 0
                    while network_attempts < 3:
                        try:
                            pause_search(page)
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
                            break
                        except Exception as exc:
                            if is_network_error(exc) or is_offline(page):
                                network_attempts += 1
                                if handle_offline_outage(
                                    page,
                                    f"{keyword} | {location}",
                                ):
                                    if network_attempts < 3:
                                        continue
                                # Offline timeout already saved Excel and set stop_requested.
                                break
                            import traceback

                            print(f"  Keyword failed ({keyword} | {location}): {exc}")
                            print(traceback.format_exc())
                            break
                    if stop_requested:
                        break

                location_start = 0
                if stop_requested:
                    break
        finally:
            _stop_battery_watcher()
            _stop_stop_watcher()
            flush_active_save(force_excel=jobs_collected > 0)
            if stop_requested or progress.get("interrupted"):
                progress["interrupted"] = True
                sync_checkpoint_context(progress)
                save_checkpoint(progress)
            else:
                clear_checkpoint()

    if stop_requested:
        file_name = os.path.basename(daily_excel_path())
        if _low_battery_triggered:
            print(
                f'\nLow-battery stop — jobs saved. Check "{file_name}" in Output. '
                "Laptop shutdown was requested."
            )
        else:
            print(
                f"\nStopped — progress saved. Check \"{file_name}\" in Output."
            )
    else:
        if jobs_collected:
            file_name = os.path.basename(daily_excel_path())
            print(f'\nScraping completed. Check "{file_name}" in Output.')
        else:
            print("\nNo jobs found.")


if __name__ == "__main__":
    run()
