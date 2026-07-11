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


def _apply_job_overrides(config):
    import job.config as cfg

    keywords = config.get("keywords")
    locations = config.get("locations")
    if keywords:
        cfg.JOB_KEYWORDS = keywords if isinstance(keywords, list) else [keywords]
    if locations:
        cfg.LOCATIONS = locations if isinstance(locations, list) else [locations]
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


def _apply_connection_overrides(config):
    import connections.config as cfg

    keywords = config.get("keywords")
    locations = config.get("locations")
    if keywords:
        cfg.CONNECTION_KEYWORDS = keywords if isinstance(keywords, list) else [keywords]
    if locations:
        cfg.CONNECTION_LOCATIONS = locations if isinstance(locations, list) else [locations]
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


def _run_job(task):
    from job.job import run
    from job.scrape_state import clear_checkpoint

    config = task.config or {}
    os.environ["TERRA_NONINTERACTIVE"] = "1"
    _apply_job_overrides(config)

    if not config.get("resume", False):
        clear_checkpoint()

    _patch_noninteractive("2")
    run()


def _run_connection(task):
    from connections.connection import run

    config = task.config or {}
    _apply_connection_overrides(config)
    keywords = config.get("keywords")
    locations = config.get("locations")
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    if isinstance(locations, str):
        locations = [l.strip() for l in locations.split(",") if l.strip()]
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
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    _setup_path()

    from apps.linkedin.models import ActivityEvent, ScraperTask
    from apps.linkedin.services.automation_bridge import install_automation_hooks

    task = ScraperTask.objects.get(pk=task_id)
    install_automation_hooks(task)
    _log(task, "info", f"Starting {task.get_task_type_display()}...")

    handlers = {
        ScraperTask.TASK_JOB: _run_job,
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
        task.mark_finished(ScraperTask.STATUS_COMPLETED)
        completion_msg = (task.progress or {}).get("completion_message")
        if not completion_msg and task.task_type == ScraperTask.TASK_JOB:
            from apps.linkedin.services.job_output_service import finalize_job_output

            output_path = finalize_job_output()
            if output_path:
                file_name = os.path.basename(output_path)
                completion_msg = f'Scraping completed. Check "{file_name}" in Output.'
            else:
                from datetime import date

                from apps.linkedin.services.config_service import load_settings

                prefix = load_settings().get("output", {}).get("file_prefix", "aniket_projectmate")
                file_name = f"{prefix}_{date.today():%Y-%m-%d}.xlsx"
                completion_msg = f'Scraping completed. Check "{file_name}" in Output.'
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
        if task.task_type == ScraperTask.TASK_JOB:
            try:
                from apps.linkedin.services.job_output_service import finalize_job_output

                finalize_job_output()
            except Exception:
                pass
        ActivityEvent.objects.create(
            event_type=task.task_type,
            title=f"{task.get_task_type_display()} failed",
            detail=str(exc)[:500],
        )
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m apps.linkedin.services.run_worker <task_id>")
        sys.exit(1)
    run_task(int(sys.argv[1]))
