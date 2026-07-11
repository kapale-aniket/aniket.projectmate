"""Settings form mapping helpers for LinkedIn admin."""
import json

from apps.linkedin.services.config_service import (
    get_excel_format,
    normalize_cursor_settings,
    normalize_max_job_age_hours,
)
from apps.linkedin.services.excel_format_service import parse_excel_format_json
from apps.linkedin.models import ScraperTask


def is_config_locked(active_task, task_type=None, settings_tab=None):
    if not active_task or not active_task.is_active:
        return False
    if settings_tab:
        tab_map = {
            "job": ScraperTask.TASK_JOB,
            "connection": ScraperTask.TASK_CONNECTION,
            "posts": ScraperTask.TASK_POSTS,
        }
        return tab_map.get(settings_tab) == active_task.task_type
    return task_type == active_task.task_type


def config_lock_message(active_task):
    if not active_task:
        return ""
    return (
        f"{active_task.get_task_type_display()} is {active_task.status}. "
        "Stop it before changing settings."
    )


def settings_to_form(app_settings, tab):
    job = app_settings.get("job", {})
    conn = app_settings.get("connection", {})
    posts = app_settings.get("posts", {})
    browser = app_settings.get("browser", {})
    cursor = app_settings.get("cursor", {})
    return {
        "tab": tab,
        "job_keywords": "\n".join(job.get("keywords", [])),
        "job_locations": "\n".join(job.get("locations", [])),
        "job_max_pages": job.get("max_pages", 40),
        "job_max_jobs": job.get("max_jobs", 0),
        "job_max_age_hours": job.get("max_job_age_hours", 24),
        "job_min_delay": job.get("search_min_delay", 1),
        "job_max_delay": job.get("search_max_delay", 2),
        "connection_keywords": "\n".join(conn.get("keywords", [])),
        "connection_locations": "\n".join(conn.get("locations", [])),
        "connection_max": conn.get("max_connections_per_run", 30),
        "connection_max_pages": conn.get("max_pages", 200),
        "posts_max_scroll": posts.get("max_scroll_rounds", 30),
        "posts_max_posts": posts.get("max_posts_per_run", 0),
        "browser_headless": browser.get("headless_default", False),
        "cursor_enabled": cursor.get("enabled", True),
        "cursor_interval_seconds": cursor.get("interval_seconds", 60),
        "job_excel_format": json.dumps(job.get("excel_format", get_excel_format("job", app_settings))),
        "connection_excel_format": json.dumps(
            conn.get("excel_format", get_excel_format("connection", app_settings))
        ),
        "posts_excel_format": json.dumps(
            posts.get("excel_format", get_excel_format("posts", app_settings))
        ),
    }


def form_to_settings(current, data):
    updated = json.loads(json.dumps(current))
    updated.setdefault("job", {})
    updated.setdefault("connection", {})
    updated.setdefault("posts", {})
    updated.setdefault("browser", {})
    updated.setdefault("cursor", {})

    updated["job"].update(
        {
            "keywords": [k.strip() for k in data.get("job_keywords", "").splitlines() if k.strip()],
            "locations": [l.strip() for l in data.get("job_locations", "").splitlines() if l.strip()],
            "max_pages": data.get("job_max_pages") or updated["job"].get("max_pages", 40),
            "max_jobs": data.get("job_max_jobs") or 0,
            "max_job_age_hours": normalize_max_job_age_hours(
                data.get("job_max_age_hours") or updated["job"].get("max_job_age_hours", 24)
            ),
            "search_min_delay": data.get("job_min_delay") or 1,
            "search_max_delay": data.get("job_max_delay") or 2,
        }
    )
    if data.get("job_excel_format"):
        updated["job"]["excel_format"] = parse_excel_format_json("job", data.get("job_excel_format"))

    updated["connection"].update(
        {
            "keywords": [
                k.strip() for k in data.get("connection_keywords", "").splitlines() if k.strip()
            ],
            "locations": [
                l.strip() for l in data.get("connection_locations", "").splitlines() if l.strip()
            ],
            "max_connections_per_run": data.get("connection_max") or 30,
            "max_pages": data.get("connection_max_pages") or 200,
        }
    )
    if data.get("connection_excel_format"):
        updated["connection"]["excel_format"] = parse_excel_format_json(
            "connection", data.get("connection_excel_format")
        )

    updated["posts"].update(
        {
            "max_scroll_rounds": data.get("posts_max_scroll") or 30,
            "max_posts_per_run": data.get("posts_max_posts") or 0,
        }
    )
    if data.get("posts_excel_format"):
        updated["posts"]["excel_format"] = parse_excel_format_json(
            "posts", data.get("posts_excel_format")
        )

    tab = data.get("tab", "job")
    if tab == "browser":
        updated["browser"]["headless_default"] = bool(data.get("browser_headless"))
    if tab == "cursor":
        updated["cursor"] = normalize_cursor_settings(
            {
                "enabled": bool(data.get("cursor_enabled")),
                "interval_seconds": data.get("cursor_interval_seconds") or 60,
            }
        )
    return updated
