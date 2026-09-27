"""Ensure job scraper output files exist after runs, stops, and crashes."""

import os
import re
from datetime import date, datetime
from pathlib import Path

from django.conf import settings

from apps.linkedin.services.automation_path import ensure_automation_path

DAILY_XLSX_PATTERN = re.compile(r"^aniket_projectmate_\d{4}-\d{2}-\d{2}\.xlsx$")
STAMPED_XLSX_PATTERN = re.compile(r"_\d{8}_\d{6}\.xlsx$")

HEADER_TO_JOB_KEY = {
    "Job Title": "job_role",
    "Job Role": "job_role",
    "Company": "company_name",
    "Company Name": "company_name",
    "Company Size": "company_size",
    "Employee Size": "company_size",
    "Experience": "experience_required",
    "Experience Required": "experience_required",
    "Skills": "skills_required",
    "Skills Required": "skills_required",
    "Location": "location",
    "Salary (LPA)": "package_lpa",
    "Package (LPA)": "package_lpa",
    "Posted": "posted_text",
    "Apply Link": "apply_link",
    "Easy Apply": "easy_apply",
    "Freshers Eligible": "freshers_eligible",
}


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


def _record_to_job(record):
    job = {}
    for header, key in HEADER_TO_JOB_KEY.items():
        if header in record and record[header] not in (None, ""):
            job[key] = record[header]
    hrefs = record.get("_hrefs") or {}
    apply_url = (
        hrefs.get("Apply")
        or hrefs.get("Apply Link")
        or hrefs.get("Job Title")
        or hrefs.get("Job Role")
        or job.get("apply_link")
        or ""
    )
    if apply_url:
        job["apply_link"] = str(apply_url).strip()
    return job if job.get("job_role") or job.get("apply_link") else None


def _jobs_from_excel(path_str):
    from apps.linkedin.services.stats import _read_xlsx_preview_records

    _headers, records = _read_xlsx_preview_records(path_str, limit=10000)
    jobs = []
    for record in records:
        job = _record_to_job(record)
        if job:
            jobs.append(job)
    return jobs


def _refresh_excel_from_jobs(jobs, excel_path):
    from job.excel_writer import write_branded_excel

    if not jobs:
        return False
    write_branded_excel(jobs, str(excel_path))
    return True


def refresh_all_job_output_excel(include_merged=True, include_orphan_xlsx=True):
    """
    Re-generate existing job Excel files from JSON backups (or re-read xlsx data)
    using the current export layout and clickable Apply links.
    """
    ensure_automation_path()
    from job.master_store import (
        DAILY_JSON_PATTERN,
        OUTPUT_DIR,
        _read_jobs_from_json,
        daily_excel_path,
    )

    output_dir = Path(OUTPUT_DIR)
    refreshed = []
    skipped = []
    errors = []

    for json_path in sorted(output_dir.glob("aniket_projectmate_*.json")):
        match = DAILY_JSON_PATTERN.match(json_path.name)
        if not match:
            continue
        day_str = match.group(1)
        jobs = _read_jobs_from_json(str(json_path))
        if not jobs:
            skipped.append(str(json_path))
            continue
        excel_path = daily_excel_path(datetime.strptime(day_str, "%Y-%m-%d").date())
        try:
            if _refresh_excel_from_jobs(jobs, excel_path):
                refreshed.append(str(excel_path))
        except Exception as exc:
            errors.append({"path": str(excel_path), "error": str(exc)})

    if include_merged or include_orphan_xlsx:
        for xlsx_path in sorted(output_dir.glob("*.xlsx")):
            name = xlsx_path.name
            if STAMPED_XLSX_PATTERN.search(name):
                continue
            if DAILY_XLSX_PATTERN.match(name):
                continue
            if name.startswith("merged_"):
                if not include_merged:
                    continue
            elif not (include_orphan_xlsx and name.startswith("aniket_projectmate_")):
                continue
            try:
                jobs = _jobs_from_excel(str(xlsx_path))
                if _refresh_excel_from_jobs(jobs, xlsx_path):
                    refreshed.append(str(xlsx_path))
                else:
                    skipped.append(str(xlsx_path))
            except Exception as exc:
                errors.append({"path": str(xlsx_path), "error": str(exc)})

    return {
        "ok": not errors,
        "refreshed": refreshed,
        "refreshed_count": len(refreshed),
        "skipped": skipped,
        "errors": errors,
    }


def finalize_job_output(day=None, scrape_mode=None):
    """Create or refresh today's Excel from the daily JSON backup.

    scrape_mode: 'job' (default) or 'perfect_match' — selects file prefix / sheet title.
    """
    ensure_automation_path()
    import job.config as cfg

    previous_mode = getattr(cfg, "SCRAPE_MODE", "job")
    previous_title = getattr(cfg, "SHEET_TITLE", "")
    mode = (scrape_mode or previous_mode or "job").strip().lower()
    cfg.SCRAPE_MODE = mode
    if mode == "perfect_match":
        cfg.SHEET_TITLE = "skill match job"

    try:
        from job.master_store import (
            daily_excel_path,
            daily_json_path,
            ensure_daily_excel,
            load_today_store,
            purge_old_files,
        )
        from job.excel_writer import write_branded_excel

        try:
            purge_old_files()
        except Exception:
            pass

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
    finally:
        cfg.SCRAPE_MODE = previous_mode
        cfg.SHEET_TITLE = previous_title


def worker_env_extras():
    extras = {
        "TERRA_DATA_DIR": str(settings.LINKEDIN_DATA_DIR),
    }
    try:
        from apps.linkedin.services.config_service import load_settings, normalize_power_settings

        power = normalize_power_settings(load_settings().get("power", {}))
        extras["TERRA_BATTERY_SHUTDOWN_PERCENT"] = str(power.get("shutdown_percent", 3))
    except Exception:
        extras["TERRA_BATTERY_SHUTDOWN_PERCENT"] = "3"
    return extras
