import json
import os
from pathlib import Path

from django.conf import settings

from apps.linkedin.services.excel_format_service import (
    default_connection_excel_format,
    default_job_excel_format,
    default_posts_excel_format,
    normalize_excel_format,
)

SETTINGS_FILE = settings.LINKEDIN_DATA_DIR / "app_settings.json"

DEFAULT_SETTINGS = {
    "job": {
        "keywords": [
            "Python Developer Fresher",
            "Java Developer Fresher",
            "Data Analyst Fresher",
            "Associate Software Engineer",
            "Software Engineer",
            "Graduate Engineer Trainee",
        ],
        "locations": ["Pune", "Bangalore"],
        "max_pages": 40,
        "max_jobs": 0,
        "max_job_age_hours": 24,
        "search_min_delay": 1,
        "search_max_delay": 2,
        "headless": False,
        "auto_resume": True,
    },
    "connection": {
        "keywords": [
            "Python Team Lead",
            "Python Recruiter",
            "HR Recruiter",
        ],
        "locations": ["Pune", "Bangalore"],
        "max_connections_per_run": 30,
        "max_pages": 200,
        "min_delay": 1,
        "max_delay": 2,
        "scroll_rounds": 6,
        "search_min_delay": 1,
        "search_max_delay": 2,
        "headless": False,
    },
    "posts": {
        "max_scroll_rounds": 30,
        "max_posts_per_run": 0,
        "search_min_delay": 1,
        "search_max_delay": 2,
        "headless": False,
    },
    "browser": {
        "headless_default": False,
        "block_images": True,
    },
    "output": {
        "file_prefix": "aniket_projectmate",
    },
    "cursor": {
        "enabled": True,
        "interval_seconds": 60,
    },
}

EXCEL_FORMAT_DEFAULTS = {
    "job": default_job_excel_format,
    "connection": default_connection_excel_format,
    "posts": default_posts_excel_format,
}


def get_excel_format(scraper_type, app_settings=None):
    app_settings = app_settings or load_settings()
    section = app_settings.get(scraper_type, {})
    raw = section.get("excel_format")
    if raw:
        return normalize_excel_format(scraper_type, raw)
    return EXCEL_FORMAT_DEFAULTS[scraper_type]()


def normalize_cursor_settings(data):
    """Dashboard-only: keep screen awake while scrapers run in the app."""
    defaults = DEFAULT_SETTINGS["cursor"]
    if not isinstance(data, dict):
        data = {}
    try:
        interval = int(data.get("interval_seconds", defaults["interval_seconds"]))
    except (TypeError, ValueError):
        interval = defaults["interval_seconds"]
    return {
        "enabled": bool(data.get("enabled", defaults["enabled"])),
        "interval_seconds": max(15, min(600, interval)),
    }


def _deep_merge(base, override):
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as handle:
                stored = json.load(handle)
            merged = _deep_merge(DEFAULT_SETTINGS, stored)
            for scraper_type in ("job", "connection", "posts"):
                section = merged.get(scraper_type, {})
                if section.get("excel_format"):
                    section["excel_format"] = normalize_excel_format(
                        scraper_type, section["excel_format"]
                    )
                else:
                    section["excel_format"] = EXCEL_FORMAT_DEFAULTS[scraper_type]()
            merged["cursor"] = normalize_cursor_settings(merged.get("cursor", {}))
            return merged
        except (OSError, json.JSONDecodeError):
            pass
    base = json.loads(json.dumps(DEFAULT_SETTINGS))
    for scraper_type in ("job", "connection", "posts"):
        base[scraper_type]["excel_format"] = EXCEL_FORMAT_DEFAULTS[scraper_type]()
    base["cursor"] = normalize_cursor_settings(base.get("cursor", {}))
    return base


def normalize_max_job_age_hours(value, default=24):
    from apps.linkedin.services.automation_path import ensure_automation_path

    ensure_automation_path()
    from common.job_age import normalize_job_age_hours

    return normalize_job_age_hours(value, default=default)


def save_settings(data):
    settings.LINKEDIN_DATA_DIR.mkdir(parents=True, exist_ok=True)
    merged = _deep_merge(DEFAULT_SETTINGS, data)
    for scraper_type in ("job", "connection", "posts"):
        section = merged.get(scraper_type, {})
        if "excel_format" in section:
            section["excel_format"] = normalize_excel_format(
                scraper_type, section["excel_format"]
            )
    merged["cursor"] = normalize_cursor_settings(merged.get("cursor", {}))
    if "job" in merged:
        merged["job"]["max_job_age_hours"] = normalize_max_job_age_hours(
            merged["job"].get("max_job_age_hours", 24)
        )
    with open(SETTINGS_FILE, "w", encoding="utf-8") as handle:
        json.dump(merged, handle, indent=2)
    sync_to_automation_configs(merged)
    sync_excel_format_files(merged)
    return merged


def sync_excel_format_files(app_settings):
    root = Path(settings.LINKEDIN_AUTOMATION_ROOT) / "config" / "excel_format"
    root.mkdir(parents=True, exist_ok=True)
    for scraper_type in ("job", "connection", "posts"):
        fmt = get_excel_format(scraper_type, app_settings)
        path = root / f"{scraper_type}.json"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(fmt, handle, indent=2)


def sync_to_automation_configs(app_settings):
    root = Path(settings.LINKEDIN_AUTOMATION_ROOT)
    job_cfg = app_settings.get("job", {})
    conn_cfg = app_settings.get("connection", {})
    posts_cfg = app_settings.get("posts", {})

    _write_python_config(
        root / "job" / "config.py",
        {
            "JOB_KEYWORDS": job_cfg.get("keywords", []),
            "LOCATIONS": job_cfg.get("locations", []),
            "MAX_PAGES": job_cfg.get("max_pages", 40),
            "MAX_JOBS": job_cfg.get("max_jobs", 0),
            "MAX_JOB_AGE_HOURS": job_cfg.get("max_job_age_hours", 24),
            "SEARCH_MIN_DELAY": job_cfg.get("search_min_delay", 1),
            "SEARCH_MAX_DELAY": job_cfg.get("search_max_delay", 2),
        },
        extra_lines=["RESULTS_PER_PAGE = 25"],
    )

    geo_urns = {
        "pune": "102713980",
        "bangalore": "105214831",
        "bengaluru": "105214831",
    }
    _write_python_config(
        root / "connections" / "config.py",
        {
            "MAX_CONNECTIONS_PER_RUN": conn_cfg.get("max_connections_per_run", 30),
            "MIN_DELAY": conn_cfg.get("min_delay", 1),
            "MAX_DELAY": conn_cfg.get("max_delay", 2),
            "SCROLL_ROUNDS": conn_cfg.get("scroll_rounds", 6),
            "MAX_PAGES": conn_cfg.get("max_pages", 200),
            "SEARCH_MIN_DELAY": conn_cfg.get("search_min_delay", 1),
            "SEARCH_MAX_DELAY": conn_cfg.get("search_max_delay", 2),
            "CONNECTION_KEYWORDS": conn_cfg.get("keywords", []),
            "CONNECTION_LOCATIONS": conn_cfg.get("locations", []),
            "LOCATION_GEO_URNS": geo_urns,
        },
    )

    _write_python_config(
        root / "posts" / "config.py",
        {
            "MAX_SCROLL_ROUNDS": posts_cfg.get("max_scroll_rounds", 30),
            "MAX_POSTS_PER_RUN": posts_cfg.get("max_posts_per_run", 0),
            "SEARCH_MIN_DELAY": posts_cfg.get("search_min_delay", 1),
            "SEARCH_MAX_DELAY": posts_cfg.get("search_max_delay", 2),
        },
    )


def _write_python_config(path, values, extra_lines=None):
    lines = ["import os", ""]
    for key, value in values.items():
        if key == "MAX_JOBS":
            lines.append(f'{key} = int(os.getenv("MAX_JOBS", "{value}"))')
        else:
            lines.append(f"{key} = {repr(value)}")
    if extra_lines:
        lines.extend(extra_lines)
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
