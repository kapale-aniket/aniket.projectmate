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
        "sheet_title": job.get("sheet_title", ""),
        "whatsapp_group_url": job.get("whatsapp_group_url", ""),
        "whatsapp_group_name": job.get("whatsapp_group_name", ""),
        "instagram_url": job.get("instagram_url", ""),
        "instagram_handle": job.get("instagram_handle", ""),
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
            "sheet_title": data.get("sheet_title") or updated["job"].get("sheet_title", ""),
            "whatsapp_group_url": data.get("whatsapp_group_url") or "",
            "whatsapp_group_name": data.get("whatsapp_group_name") or "",
            "instagram_url": data.get("instagram_url") or "",
            "instagram_handle": data.get("instagram_handle") or "",
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


def persist_run_config_to_settings(task_type, config):
    """Remember last run keywords/locations in app settings for the next visit."""
    from apps.linkedin.services.config_service import load_settings, save_settings

    if not config:
        return

    app_settings = load_settings()

    if task_type == ScraperTask.TASK_JOB:
        job = app_settings.setdefault("job", {})
        if config.get("keywords"):
            job["keywords"] = list(config["keywords"])
        if config.get("locations"):
            job["locations"] = list(config["locations"])
        if config.get("max_pages") is not None:
            job["max_pages"] = int(config["max_pages"])
        if config.get("max_jobs") is not None:
            job["max_jobs"] = int(config["max_jobs"])
        if config.get("max_job_age_hours") is not None:
            job["max_job_age_hours"] = normalize_max_job_age_hours(config["max_job_age_hours"])
        if "skip_previous_jobs" in config:
            job["skip_previous_jobs"] = bool(config["skip_previous_jobs"])
    elif task_type == ScraperTask.TASK_CONNECTION:
        conn = app_settings.setdefault("connection", {})
        if config.get("keywords"):
            conn["keywords"] = list(config["keywords"])
        if config.get("locations"):
            conn["locations"] = list(config["locations"])
        if config.get("max_connections_per_run") is not None:
            conn["max_connections_per_run"] = int(config["max_connections_per_run"])
        if config.get("max_pages") is not None:
            conn["max_pages"] = int(config["max_pages"])
    elif task_type == ScraperTask.TASK_POSTS:
        posts = app_settings.setdefault("posts", {})
        if config.get("max_scroll_rounds") is not None:
            posts["max_scroll_rounds"] = int(config["max_scroll_rounds"])
        if config.get("max_posts_per_run") is not None:
            posts["max_posts_per_run"] = int(config["max_posts_per_run"])

    save_settings(app_settings)


def apply_last_task_form_defaults(form, task_type):
    """Prefer the most recent scraper run over static default keywords."""
    task = (
        ScraperTask.objects.filter(task_type=task_type)
        .order_by("-created_at")
        .first()
    )
    if not task or not task.config:
        return

    cfg = task.config
    if task_type == ScraperTask.TASK_JOB:
        if cfg.get("keywords"):
            form.fields["keywords"].initial = "\n".join(cfg["keywords"])
        if cfg.get("locations"):
            form.fields["locations"].initial = "\n".join(cfg["locations"])
        if cfg.get("max_pages") is not None:
            form.fields["max_pages"].initial = cfg["max_pages"]
        if cfg.get("max_jobs") is not None:
            form.fields["max_jobs"].initial = cfg["max_jobs"]
        if cfg.get("max_job_age_hours") is not None:
            form.fields["max_job_age_hours"].initial = cfg["max_job_age_hours"]
        if "skip_previous_jobs" in cfg:
            form.fields["skip_previous_jobs"].initial = bool(cfg["skip_previous_jobs"])
        if "resume" in cfg:
            form.fields["resume"].initial = bool(cfg["resume"])
    elif task_type == ScraperTask.TASK_CONNECTION:
        if cfg.get("keywords"):
            form.fields["keywords"].initial = "\n".join(cfg["keywords"])
        if cfg.get("locations"):
            form.fields["locations"].initial = "\n".join(cfg["locations"])
        if cfg.get("max_connections_per_run") is not None:
            form.fields["max_connections_per_run"].initial = cfg["max_connections_per_run"]
        if cfg.get("max_pages") is not None:
            form.fields["max_pages"].initial = cfg["max_pages"]
    elif task_type == ScraperTask.TASK_POSTS:
        if cfg.get("max_scroll_rounds") is not None:
            form.fields["max_scroll_rounds"].initial = cfg["max_scroll_rounds"]
        if cfg.get("max_posts_per_run") is not None:
            form.fields["max_posts_per_run"].initial = cfg["max_posts_per_run"]
