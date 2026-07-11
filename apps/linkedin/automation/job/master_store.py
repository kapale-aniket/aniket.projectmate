import glob
import json
import os
import re
from datetime import date, datetime

from job.job_filter import job_id_from_url

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
FILE_PREFIX = "aniket_projectmate"
DAILY_JSON_PATTERN = re.compile(rf"^{re.escape(FILE_PREFIX)}_(\d{{4}}-\d{{2}}-\d{{2}})\.json$")
LEGACY_JSON = os.path.join(OUTPUT_DIR, f"{FILE_PREFIX}_master.json")


def _resolve_day(day=None):
    return day or date.today()


def daily_json_path(day=None):
    day_str = _resolve_day(day).strftime("%Y-%m-%d")
    return os.path.join(OUTPUT_DIR, f"{FILE_PREFIX}_{day_str}.json")


def daily_excel_path(day=None):
    day_str = _resolve_day(day).strftime("%Y-%m-%d")
    return os.path.join(OUTPUT_DIR, f"{FILE_PREFIX}_{day_str}.xlsx")


def _parse_date(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _read_jobs_from_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError):
        return []
    if isinstance(data, list):
        return data
    jobs = data.get("jobs")
    return jobs if isinstance(jobs, list) else []


def job_ids_from_jobs(jobs):
    ids = set()
    for job in jobs:
        job_id = job_id_from_url(job.get("apply_link", ""))
        if job_id:
            ids.add(job_id)
    return ids


def known_job_ids():
    ids = set()
    if os.path.exists(LEGACY_JSON):
        ids |= job_ids_from_jobs(_read_jobs_from_json(LEGACY_JSON))
    for path in glob.glob(os.path.join(OUTPUT_DIR, f"{FILE_PREFIX}_*.json")):
        basename = os.path.basename(path)
        if basename == f"{FILE_PREFIX}_master.json":
            continue
        if not DAILY_JSON_PATTERN.match(basename):
            continue
        ids |= job_ids_from_jobs(_read_jobs_from_json(path))
    return ids


def count_previous_daily_files(day=None):
    today = _resolve_day(day)
    count = 0
    for path in glob.glob(os.path.join(OUTPUT_DIR, f"{FILE_PREFIX}_*.json")):
        match = DAILY_JSON_PATTERN.match(os.path.basename(path))
        if not match:
            continue
        file_day = _parse_date(match.group(1))
        if file_day and file_day < today:
            count += 1
    return count


def load_today_store(day=None):
    today = _resolve_day(day)
    empty_store = {"date": today.strftime("%Y-%m-%d"), "jobs": []}
    path = daily_json_path(today)
    if not os.path.exists(path):
        return empty_store
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError):
        return empty_store
    jobs = data.get("jobs")
    return {
        "date": data.get("date", empty_store["date"]),
        "jobs": jobs if isinstance(jobs, list) else [],
    }


def save_today_store(store, day=None):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(daily_json_path(day), "w", encoding="utf-8") as handle:
        json.dump(store, handle, ensure_ascii=False, indent=2)


def load_all_previous_jobs(day=None):
    """Return jobs from all daily JSON files before today."""
    today = _resolve_day(day)
    jobs = []
    for path in glob.glob(os.path.join(OUTPUT_DIR, f"{FILE_PREFIX}_*.json")):
        match = DAILY_JSON_PATTERN.match(os.path.basename(path))
        if not match:
            continue
        file_day = _parse_date(match.group(1))
        if file_day and file_day < today:
            jobs.extend(_read_jobs_from_json(path))
    return jobs


def summarize_known_jobs(day=None):
    """Print-friendly summary of jobs loaded from previous daily files."""
    today = _resolve_day(day)
    previous_files = []
    for path in glob.glob(os.path.join(OUTPUT_DIR, f"{FILE_PREFIX}_*.json")):
        match = DAILY_JSON_PATTERN.match(os.path.basename(path))
        if not match:
            continue
        file_day = _parse_date(match.group(1))
        if not file_day or file_day >= today:
            continue
        jobs = _read_jobs_from_json(path)
        previous_files.append((match.group(1), len(jobs)))

    previous_files.sort()
    return previous_files


def ensure_daily_excel(today_store, day=None):
    """Create today's Excel from JSON when the workbook is missing."""
    excel_path = daily_excel_path(day)
    if os.path.exists(excel_path):
        return excel_path
    if not today_store.get("jobs"):
        return excel_path
    from job.excel_writer import write_branded_excel

    write_branded_excel(today_store["jobs"], excel_path)
    return excel_path
