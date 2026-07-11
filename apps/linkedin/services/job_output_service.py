"""Ensure job scraper output files exist after runs, stops, and crashes."""

import os
from datetime import date
from pathlib import Path

from django.conf import settings

from apps.linkedin.services.automation_path import ensure_automation_path


def stop_flag_path(task_id):
    return Path(settings.LINKEDIN_DATA_DIR) / f"stop_task_{task_id}"


def request_task_stop(task_id):
    settings.LINKEDIN_DATA_DIR.mkdir(parents=True, exist_ok=True)
    stop_flag_path(task_id).write_text("1", encoding="utf-8")


def clear_task_stop_flag(task_id):
    try:
        stop_flag_path(task_id).unlink()
    except OSError:
        pass


def finalize_job_output(day=None):
    """Create or refresh today's Excel from the daily JSON backup."""
    ensure_automation_path()
    from job.master_store import (
        daily_excel_path,
        daily_json_path,
        ensure_daily_excel,
        load_today_store,
    )
    from job.excel_writer import write_branded_excel

    target_day = day or date.today()
    store = load_today_store(target_day)
    json_path = Path(daily_json_path(target_day))
    excel_path = Path(daily_excel_path(target_day))

    if store.get("jobs"):
        if not json_path.is_file():
            from job.master_store import save_today_store

            save_today_store(store, target_day)
        try:
            write_branded_excel(store["jobs"], str(excel_path))
        except Exception:
            try:
                ensure_daily_excel(store, target_day)
            except Exception:
                if excel_path.is_file():
                    return str(excel_path)
                raise
        return str(excel_path) if excel_path.is_file() else None

    if excel_path.is_file():
        return str(excel_path)

    if json_path.is_file():
        try:
            ensure_daily_excel(store, target_day)
        except Exception:
            pass
        if excel_path.is_file():
            return str(excel_path)

    return None


def worker_env_extras():
    return {
        "TERRA_DATA_DIR": str(settings.LINKEDIN_DATA_DIR),
    }
