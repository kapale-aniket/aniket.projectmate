"""
Subprocess worker for running LinkedIn automation tasks from the Django UI.
Invoked as: python -m apps.linkedin.services.run_worker <task_id>
"""

import builtins
import json
import os
import sys
import traceback
from pathlib import Path


def _setup_path():
    from django.conf import settings

    automation_root = str(settings.LINKEDIN_AUTOMATION_ROOT)
    if automation_root not in sys.path:
        sys.path.insert(0, automation_root)


def _patch_noninteractive(resume_choice="2"):
    original_input = builtins.input

    def fake_input(prompt=""):
        print(prompt, flush=True)
        print(f"[Aniket.Project Mate] Auto-selecting option {resume_choice}", flush=True)
        return resume_choice

    builtins.input = fake_input
    return original_input


def _log(task, level, message):
    from apps.linkedin.models import TaskLog

    TaskLog.objects.create(task=task, level=level, message=message)
    print(message, flush=True)


def _as_keyword_list(value):
    if not value:
        return None
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.replace(",", "\n").splitlines() if part.strip()]
    text = str(value).strip()
    return [text] if text else None


def _apply_job_overrides(config):
    import job.config as cfg

    keywords = _as_keyword_list(config.get("keywords"))
    locations = _as_keyword_list(config.get("locations"))
    if keywords:
        cfg.JOB_KEYWORDS = keywords
    if locations:
        cfg.LOCATIONS = locations
    if config.get("max_pages") is not None:
        cfg.MAX_PAGES = int(config["max_pages"])
    if config.get("max_jobs") is not None:
        cfg.MAX_JOBS = int(config["max_jobs"])
    if config.get("max_job_age_hours") is not None:
        from apps.linkedin.services.automation_path import ensure_automation_path

        ensure_automation_path()
        from common.job_age import normalize_job_age_hours

        cfg.MAX_JOB_AGE_HOURS = normalize_job_age_hours(config["max_job_age_hours"])
    if config.get("search_min_delay") is not None:
        cfg.SEARCH_MIN_DELAY = float(config["search_min_delay"])
    if config.get("search_max_delay") is not None:
        cfg.SEARCH_MAX_DELAY = float(config["search_max_delay"])
    cfg.SKIP_SEARCHES = list(config.get("skip_searches") or [])
    cfg.SKIP_PREVIOUS_JOBS = bool(config.get("skip_previous_jobs", False))
    scrape_mode = (config.get("scrape_mode") or "job").strip().lower()
    cfg.SCRAPE_MODE = scrape_mode
    skills = _as_keyword_list(config.get("skills")) or []
    cfg.PERFECT_MATCH_SKILLS = skills
    cfg.PERFECT_MATCH_EXPERIENCE = str(config.get("experience") or "").strip()
    try:
        cfg.PERFECT_MATCH_MIN_SKILLS = max(1, int(config.get("min_skills_match") or 1))
    except (TypeError, ValueError):
        cfg.PERFECT_MATCH_MIN_SKILLS = 1
    if scrape_mode == "perfect_match":
        cfg.SHEET_TITLE = "skill match job"
        # Always one combined skills query × each location (not one search per skill).
        if skills:
            cfg.JOB_KEYWORDS = [" ".join(skills)]
            cfg.PERFECT_MATCH_MIN_SKILLS = min(cfg.PERFECT_MATCH_MIN_SKILLS, len(skills))
        elif keywords:
            # Legacy: if only keywords were sent, still collapse to one search string.
            cfg.JOB_KEYWORDS = [" ".join(keywords)]
            cfg.PERFECT_MATCH_SKILLS = keywords
            cfg.PERFECT_MATCH_MIN_SKILLS = min(cfg.PERFECT_MATCH_MIN_SKILLS, len(keywords))
        else:
            cfg.JOB_KEYWORDS = []


def _apply_connection_overrides(config):
    import connections.config as cfg

    keywords = _as_keyword_list(config.get("keywords"))
    locations = _as_keyword_list(config.get("locations"))
    if keywords:
        cfg.CONNECTION_KEYWORDS = keywords
    if locations:
        cfg.CONNECTION_LOCATIONS = locations
    if config.get("max_connections_per_run") is not None:
        cfg.MAX_CONNECTIONS_PER_RUN = int(config["max_connections_per_run"])
    if config.get("max_pages") is not None:
        cfg.MAX_PAGES = int(config["max_pages"])


def _apply_posts_overrides(config):
    import posts.config as cfg

    if config.get("max_scroll_rounds") is not None:
        cfg.MAX_SCROLL_ROUNDS = int(config["max_scroll_rounds"])
    if config.get("max_posts_per_run") is not None:
        cfg.MAX_POSTS_PER_RUN = int(config["max_posts_per_run"])


def _sync_job_module_from_config(job_module):
    """job.py imports config values by name; keep those names in sync after overrides."""
    import job.config as cfg

    for name in (
        "JOB_KEYWORDS",
        "LOCATIONS",
        "MAX_PAGES",
        "MAX_JOBS",
        "MAX_JOB_AGE_HOURS",
        "SEARCH_MIN_DELAY",
        "SEARCH_MAX_DELAY",
        "SKIP_SEARCHES",
        "SKIP_PREVIOUS_JOBS",
        "SCRAPE_MODE",
        "PERFECT_MATCH_SKILLS",
        "PERFECT_MATCH_EXPERIENCE",
        "PERFECT_MATCH_MIN_SKILLS",
        "SHEET_TITLE",
        "RESULTS_PER_PAGE",
        "JOB_SEARCH_DISTANCE_KM",
        "JOB_SEARCH_SORT_BY",
    ):
        if hasattr(cfg, name):
            setattr(job_module, name, getattr(cfg, name))


def _run_job(task):
    import importlib

    import job.config as cfg
    import job.job_filter
    import job.job as job_module
    import job.master_store as store_module
    import job.scrape_state as scrape_state_module

    config = dict(task.config or {})
    if task.task_type == "perfect_match" or (config.get("scrape_mode") or "").strip().lower() == "perfect_match":
        config["scrape_mode"] = "perfect_match"

    # Apply overrides first, then reload workers, then re-apply + sync bound names.
    # (job.py does `from job.config import JOB_KEYWORDS` so reload alone keeps stale lists.)
    _apply_job_overrides(config)
    importlib.reload(cfg)
    _apply_job_overrides(config)
    importlib.reload(store_module)
    importlib.reload(scrape_state_module)
    importlib.reload(job.job_filter)
    importlib.reload(job_module)
    _apply_job_overrides(config)
    _sync_job_module_from_config(job_module)
    if hasattr(job_module, "refresh_runtime_search_config"):
        job_module.refresh_runtime_search_config()

    run = job_module.run
    from job.scrape_state import clear_checkpoint, load_checkpoint, search_plan_signature

    os.environ["TERRA_NONINTERACTIVE"] = "1"
    from apps.linkedin.services.search_skip_service import write_skip_searches

    write_skip_searches(task.id, config.get("skip_searches") or [])

    # Never resume Jobs keywords into Perfect Match (or any changed plan).
    resume = bool(config.get("resume", False))
    plan = search_plan_signature(
        list(getattr(cfg, "JOB_KEYWORDS", []) or []),
        list(getattr(cfg, "LOCATIONS", []) or []),
    )
    checkpoint = load_checkpoint()
    if not resume or checkpoint.get("search_plan") != plan:
        clear_checkpoint()
        resume = False
        config["resume"] = False

    print(
        f"Job overrides: mode={getattr(job_module, 'SCRAPE_MODE', '?')} "
        f"keywords={list(getattr(job_module, 'JOB_KEYWORDS', []) or [])} "
        f"locations={list(getattr(job_module, 'LOCATIONS', []) or [])} "
        f"skills={list(getattr(job_module, 'PERFECT_MATCH_SKILLS', []) or [])}",
        flush=True,
    )

    _patch_noninteractive("2")
    run(allow_resume=resume)


def _run_perfect_match(task):
    config = dict(task.config or {})
    config["scrape_mode"] = "perfect_match"
    skills = config.get("skills") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.splitlines() if s.strip()]
    if skills:
        config["skills"] = list(skills)
        config["keywords"] = [" ".join(str(s).strip() for s in skills if str(s).strip())]
    task.config = config
    _run_job(task)


def _run_connection(task):
    from connections.connection import run

    config = task.config or {}
    _apply_connection_overrides(config)
    keywords = _as_keyword_list(config.get("keywords"))
    locations = _as_keyword_list(config.get("locations"))
    run(keywords=keywords or None, locations=locations or None)


def _run_posts(task):
    from posts.post_scan import run

    config = task.config or {}
    _apply_posts_overrides(config)
    run()


def _run_session(task):
    from common.save_session import main as save_session_main

    save_session_main()


def run_task(task_id):
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    _setup_path()

    from apps.linkedin.services.automation_bridge import _configure_stdout_encoding

    _configure_stdout_encoding()

    from apps.linkedin.models import ActivityEvent, ScraperTask
    from apps.linkedin.services.automation_bridge import install_automation_hooks

    task = ScraperTask.objects.get(pk=task_id)
    install_automation_hooks(task)
    _log(task, "info", f"Starting {task.get_task_type_display()}...")

    handlers = {
        ScraperTask.TASK_JOB: _run_job,
        ScraperTask.TASK_PERFECT_MATCH: _run_perfect_match,
        ScraperTask.TASK_CONNECTION: _run_connection,
        ScraperTask.TASK_POSTS: _run_posts,
        ScraperTask.TASK_SESSION: _run_session,
    }

    try:
        handler = handlers.get(task.task_type)
        if not handler:
            raise ValueError(f"Unknown task type: {task.task_type}")
        handler(task)
        task.refresh_from_db()
        if task.status == ScraperTask.STATUS_STOPPED:
            _log(task, "info", "Task stopped — partial Excel kept if jobs were collected.")
            return
        task.mark_finished(ScraperTask.STATUS_COMPLETED)
        completion_msg = (task.progress or {}).get("completion_message")
        if not completion_msg and task.task_type in (
            ScraperTask.TASK_JOB,
            ScraperTask.TASK_PERFECT_MATCH,
        ):
            if int((task.progress or {}).get("jobs_found") or 0) == 0 and (
                "no jobs found" in " ".join(
                    (log.message or "").lower() for log in task.logs.all()[:8]
                )
            ):
                completion_msg = "No jobs found."
            else:
                from apps.linkedin.services.job_output_service import finalize_job_output

                output_path = finalize_job_output()
                if output_path:
                    file_name = os.path.basename(output_path)
                    completion_msg = f'Scraping completed. Check "{file_name}" in Output.'
                else:
                    completion_msg = "No jobs found."
        if (completion_msg or "").strip().lower() == "no jobs found.":
            completion_msg = "No jobs found."
            progress = dict(task.progress or {})
            progress["completion_message"] = completion_msg
            progress["jobs_found"] = 0
            task.progress = progress
            task.save(update_fields=["progress"])
        _log(task, "success", completion_msg or f"{task.get_task_type_display()} completed successfully.")
        ActivityEvent.objects.create(
            event_type=task.task_type,
            title=f"{task.get_task_type_display()} completed",
            detail=json.dumps(task.config)[:500],
        )
    except SystemExit as exc:
        code = exc.code if exc.code is not None else 1
        if code == 0:
            task.mark_finished(ScraperTask.STATUS_COMPLETED)
            _log(task, "success", "Session saved successfully.")
        else:
            task.mark_finished(ScraperTask.STATUS_FAILED, f"Exit code {code}")
            _log(task, "error", f"Task exited with code {code}")
    except Exception as exc:
        tb = traceback.format_exc()
        task.mark_finished(ScraperTask.STATUS_FAILED, str(exc))
        _log(task, "error", f"{exc}\n{tb}")
        if task.task_type in (ScraperTask.TASK_JOB, ScraperTask.TASK_PERFECT_MATCH):
            try:
                from apps.linkedin.services.job_output_service import finalize_job_output

                mode = (
                    "perfect_match"
                    if task.task_type == ScraperTask.TASK_PERFECT_MATCH
                    else "job"
                )
                finalize_job_output(scrape_mode=mode)
            except Exception:
                pass
        ActivityEvent.objects.create(
            event_type=task.task_type,
            title=f"{task.get_task_type_display()} failed",
            detail=str(exc)[:500],
        )
        raise
    finally:
        from apps.linkedin.services.search_skip_service import clear_skip_searches

        clear_skip_searches(task.id)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m apps.linkedin.services.run_worker <task_id>")
        sys.exit(1)
    run_task(int(sys.argv[1]))
