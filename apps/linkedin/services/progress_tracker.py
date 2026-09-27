import json
import os
import re
from datetime import date
from pathlib import Path

from django.conf import settings

from apps.linkedin.models import ScraperTask


def _automation_root():
    return Path(settings.LINKEDIN_AUTOMATION_ROOT)


def parse_log_progress(task, message):
    """Extract progress hints from automation log lines."""
    progress = dict(task.progress or {})
    msg = message.lower()

    search_match = re.search(
        r"searching:\s*(.+?)\s*\|\s*(.+?)(?:\s*\(past[^)]*\))?\s*$",
        message.strip(),
        re.IGNORECASE,
    )
    if search_match:
        progress["keyword"] = search_match.group(1).strip()
        progress["location"] = search_match.group(2).strip()

    finished_match = re.search(
        r"finished\s+(\d+)/(\d+)\s+keywords,\s+(\d+)/(\d+)\s+locations:",
        msg,
    )
    if finished_match:
        kw_done = int(finished_match.group(1))
        loc_done = int(finished_match.group(3))
        loc_total = int(finished_match.group(4))
        progress["keyword_index"] = kw_done - 1
        progress["location_index"] = loc_done - 1
        progress["keywords_total"] = int(finished_match.group(2))
        progress["locations_total"] = loc_total
        progress["completed_search_index"] = (kw_done - 1) * loc_total + (loc_done - 1)

    page_match = re.search(r"finished page (\d+)", msg)
    if page_match:
        progress["page"] = int(page_match.group(1))

    jobs_match = re.search(r"(\d+) new job", msg)
    if jobs_match:
        progress["jobs_found"] = int(jobs_match.group(1))

    total_match = re.search(r"(\d+) total today", msg)
    if total_match:
        progress["jobs_found"] = int(total_match.group(1))

    conn_match = re.search(r"sent (\d+) connection", msg)
    if conn_match:
        progress["connections_sent"] = int(conn_match.group(1))

    posts_match = re.search(r"checked (\d+) new post", msg)
    if posts_match:
        progress["posts_checked"] = int(posts_match.group(1))

    hiring_match = re.search(r"(\d+) new hiring post", msg)
    if hiring_match:
        progress["hiring_posts"] = int(hiring_match.group(1))

    if "no jobs found" in msg:
        progress["jobs_found"] = 0
        progress["percent"] = 100
        progress["completion_message"] = "No jobs found."
        return progress

    if "scraping completed" in msg or "done." in msg:
        progress["percent"] = 100

    check_match = re.search(r'check "([^"]+)" in output', message, re.IGNORECASE)
    if check_match:
        file_name = check_match.group(1).strip()
        progress["output_file"] = file_name
        progress["completion_message"] = f'Scraping completed. Check "{file_name}" in Output.'

    return progress


def _read_job_checkpoint():
    state_path = _automation_root() / "job" / "output" / "scrape_state.json"
    if not state_path.exists():
        return {}
    try:
        with open(state_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def _count_today_jobs(prefix="aniket_projectmate"):
    today = date.today().strftime("%Y-%m-%d")
    json_path = _automation_root() / "job" / "output" / f"{prefix}_{today}.json"
    if not json_path.exists():
        return 0
    try:
        with open(json_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        jobs = data.get("jobs", [])
        return len(jobs) if isinstance(jobs, list) else 0
    except (OSError, json.JSONDecodeError):
        return 0


def build_job_search_checklist(task):
    """Keyword × location pairs for the job / perfect-match scraper progress list."""
    if not task or task.task_type not in (
        ScraperTask.TASK_JOB,
        ScraperTask.TASK_PERFECT_MATCH,
    ):
        return []

    config = task.config or {}
    keywords = config.get("keywords") or []
    skills = config.get("skills") or []
    # Perfect Match: always one combined skills query × locations.
    if task.task_type == ScraperTask.TASK_PERFECT_MATCH and skills:
        keywords = [" ".join(str(s).strip() for s in skills if str(s).strip())]
    elif not keywords and skills:
        keywords = list(skills)
    locations = config.get("locations") or []
    if not keywords or not locations:
        return []

    from apps.linkedin.services.automation_path import ensure_automation_path

    ensure_automation_path()
    from common.search_skip import is_search_skipped, search_pair_key

    skip_searches = config.get("skip_searches") or []
    progress = dict(task.progress or {})
    checkpoint = _read_job_checkpoint()
    kw_idx = checkpoint.get("keyword_index", progress.get("keyword_index", 0))
    loc_idx = checkpoint.get("location_index", progress.get("location_index", 0))
    current_linear = kw_idx * len(locations) + loc_idx
    completed_linear = progress.get("completed_search_index", -1)
    all_done = task.status == ScraperTask.STATUS_COMPLETED

    items = []
    for ki, keyword in enumerate(keywords):
        for li, location in enumerate(locations):
            key = search_pair_key(keyword, location)
            linear = ki * len(locations) + li
            if is_search_skipped(keyword, location, skip_searches):
                status = "skipped"
            elif all_done or linear <= completed_linear:
                status = "done"
            elif linear == current_linear and task.status in {
                ScraperTask.STATUS_PENDING,
                ScraperTask.STATUS_RUNNING,
                ScraperTask.STATUS_PAUSED,
            }:
                status = "paused" if task.status == ScraperTask.STATUS_PAUSED else "active"
            else:
                status = "pending"
            items.append(
                {
                    "id": key,
                    "keyword": keyword,
                    "location": location,
                    "status": status,
                    "label": f"{location} -> {keyword}",
                }
            )
    return items


def get_live_progress(task):
    config = task.config or {}
    progress = dict(task.progress or {})
    task_type = task.task_type

    if task_type in (ScraperTask.TASK_JOB, ScraperTask.TASK_PERFECT_MATCH):
        keywords = config.get("keywords") or []
        skills = config.get("skills") or []
        if task_type == ScraperTask.TASK_PERFECT_MATCH and skills:
            keywords = [" ".join(str(s).strip() for s in skills if str(s).strip())]
        elif not keywords and skills:
            keywords = list(skills)
        locations = config.get("locations") or []
        max_pages = int(config.get("max_pages") or 40)
        checkpoint = _read_job_checkpoint()

        kw_idx = checkpoint.get("keyword_index", progress.get("keyword_index", 0))
        loc_idx = checkpoint.get("location_index", progress.get("location_index", 0))
        page_num = checkpoint.get("page_num", 0)

        keyword = keywords[kw_idx] if kw_idx < len(keywords) else (keywords[0] if keywords else "-")
        location = locations[loc_idx] if loc_idx < len(locations) else (locations[0] if locations else "-")

        from apps.linkedin.services.automation_path import ensure_automation_path

        ensure_automation_path()
        from common.search_skip import count_active_searches

        skip_searches = config.get("skip_searches") or []
        total_searches = max(1, count_active_searches(keywords, locations, skip_searches))
        current_search = kw_idx * max(1, len(locations)) + loc_idx
        search_pct = (current_search / total_searches) * 100
        page_pct = ((page_num + 1) / max(1, max_pages)) * (100 / total_searches)
        percent = min(99, int(search_pct + page_pct)) if task.status == ScraperTask.STATUS_RUNNING else progress.get("percent", 0)
        file_prefix = (
            "skill_match_job"
            if task_type == ScraperTask.TASK_PERFECT_MATCH
            else "aniket_projectmate"
        )

        progress.update(
            {
                "keyword": progress.get("keyword") or keyword,
                "location": progress.get("location") or location,
                "page": f"{page_num + 1} / {max_pages}",
                "search_progress": f"{min(current_search + 1, total_searches)} / {total_searches}",
                "jobs_found": _count_today_jobs(prefix=file_prefix),
                "percent": percent if task.status == ScraperTask.STATUS_RUNNING else progress.get("percent", percent),
            }
        )

    elif task_type == ScraperTask.TASK_CONNECTION:
        progress.setdefault("keyword", ", ".join(config.get("keywords") or [])[:80])
        progress.setdefault("location", ", ".join(config.get("locations") or [])[:80])
        progress.setdefault("connections_sent", progress.get("connections_sent", 0))
        if task.status == ScraperTask.STATUS_RUNNING and "percent" not in progress:
            progress["percent"] = min(90, progress.get("connections_sent", 0) * 3)

    elif task_type == ScraperTask.TASK_POSTS:
        progress.setdefault("percent", 50 if task.status == ScraperTask.STATUS_RUNNING else 0)
        progress.setdefault("posts_checked", progress.get("posts_checked", 0))

    elif task_type == ScraperTask.TASK_SESSION:
        progress["percent"] = 50 if task.status == ScraperTask.STATUS_RUNNING else progress.get("percent", 0)
        progress["message"] = "Waiting for LinkedIn login in browser..."

    if task.status in {ScraperTask.STATUS_COMPLETED}:
        progress["percent"] = 100

    return progress


def update_task_progress(task, message):
    progress = parse_log_progress(task, message)
    if not progress:
        return
    merged = dict(task.progress or {})
    merged.update(progress)
    live = get_live_progress(task)
    merged.update({k: v for k, v in live.items() if k not in merged or merged[k] in (None, 0, "-")})
    task.progress = merged
    task.save(update_fields=["progress"])
