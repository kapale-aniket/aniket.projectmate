import csv
import glob
import json
import os
import re
from datetime import date, datetime
from pathlib import Path

from django.conf import settings

from apps.linkedin.models import ActivityEvent, ScraperTask, TaskLog
from apps.linkedin.services.automation_path import ensure_automation_path
from apps.linkedin.services.file_errors import friendly_file_error


def _preview_error(exc, path):
    if isinstance(exc, OSError):
        return friendly_file_error(exc, path, "preview")
    return str(exc)


def _automation_root():
    return Path(settings.LINKEDIN_AUTOMATION_ROOT)


def session_status():
    storage = _automation_root() / "common" / "storage_state.json"
    if not storage.exists():
        return {"valid": False, "message": "No session saved. Run Session Login."}
    try:
        mtime = datetime.fromtimestamp(storage.stat().st_mtime)
        with open(storage, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        cookies = data.get("cookies", [])
        has_token = any(c.get("name") == "li_at" and c.get("value") for c in cookies)
        if not has_token:
            return {"valid": False, "message": "Session file exists but login cookie missing."}
        return {
            "valid": True,
            "message": "LinkedIn session is active.",
            "updated_at": mtime.strftime("%Y-%m-%d %H:%M"),
            "path": str(storage),
        }
    except (OSError, json.JSONDecodeError) as exc:
        return {"valid": False, "message": f"Invalid session file: {exc}"}


def _jobs_from_json_data(data):
    ensure_automation_path()
    from common.tabular_io import jobs_from_json_data

    return jobs_from_json_data(data)


PREVIEW_COLUMN_ORDER = [
    "timestamp",
    "keyword",
    "location",
    "name",
    "status",
    "profile_url",
    "Profile URL",
    "job_role",
    "Job Role",
    "company_name",
    "Company Name",
    "location",
    "Location",
    "company_size",
    "Company Size",
    "freshers_eligible",
    "Freshers Eligible",
    "experience_required",
    "Experience Required",
    "skills_required",
    "Skills Required",
    "package_lpa",
    "Package (LPA)",
    "posted_text",
    "Posted",
    "easy_apply",
    "Easy Apply",
    "apply_link",
    "Apply Link",
    "_source_file",
]


PREVIEW_HIDDEN_HEADER_KEYS = frozenset(
    {
        "srno",
        "serialno",
        "serialnumber",
        "sno",
        "slno",
        "rownumber",
        "index",
        "postedhours",
    }
)


def _normalize_header_key(header):
    return re.sub(r"[\s._#-]+", "", str(header or "").strip().lower())


def filter_preview_columns(headers):
    """Drop serial-number columns from table preview (still kept in downloaded files)."""
    return [h for h in headers if _normalize_header_key(h) not in PREVIEW_HIDDEN_HEADER_KEYS]


def _order_preview_headers(headers):
    headers = filter_preview_columns(headers)
    seen = set()
    ordered = []
    for header in PREVIEW_COLUMN_ORDER:
        if header in headers and header not in seen:
            ordered.append(header)
            seen.add(header)
    for header in headers:
        if header not in seen:
            ordered.append(header)
            seen.add(header)
    return ordered


def _format_preview_cell(header, value, max_len=120):
    text = "" if value is None else str(value).strip()
    if text.startswith("http://") or text.startswith("https://"):
        return text
    return text[:max_len]


def _is_url(value):
    text = str(value or "").strip()
    return text.startswith("http://") or text.startswith("https://")


def _link_label(header, value):
    if header in {"apply_link", "Apply Link"}:
        return "Apply"
    if header in {"profile_url", "Profile URL"}:
        return "View profile"
    text = str(value or "").strip()
    if len(text) > 48:
        return text[:45] + "..."
    return text or "Open link"


def _find_xlsx_header_row(all_rows):
    ensure_automation_path()
    from common.tabular_io import find_xlsx_header_row

    return find_xlsx_header_row(all_rows)


def _rows_from_dicts(headers, records, limit=500):
    body = []
    for record in records[:limit]:
        body.append([_format_preview_cell(h, record.get(h, "")) for h in headers])
    return body


def attach_preview_rows_zipped(preview):
    if not preview or preview.get("error"):
        return preview
    headers = preview.get("headers") or []
    rows = preview.get("rows") or []
    preview["rows_zipped"] = [
        [
            {
                "header": header,
                "value": cell,
                "is_link": _is_url(cell),
                "link_label": _link_label(header, cell),
            }
            for header, cell in zip(headers, row)
        ]
        for row in rows
    ]
    return preview


def count_jobs_scraped():
    output_dir = _automation_root() / "job" / "output"
    total = 0
    for path in glob.glob(str(output_dir / "aniket_projectmate_*.json")):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            total += len(_jobs_from_json_data(data))
        except (OSError, json.JSONDecodeError):
            continue
    return total


def count_connections_sent():
    csv_path = _automation_root() / "connections" / "new_connection" / "connections_sent.csv"
    if not csv_path.exists():
        return 0
    try:
        with open(csv_path, "r", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        return max(0, len(rows) - 1)
    except OSError:
        return 0


def count_posts_scraped():
    output_dir = _automation_root() / "posts" / "output"
    state_path = output_dir / "posts_state.json"
    if not state_path.exists():
        return 0
    try:
        with open(state_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return len(data.get("hiring_posts", []))
    except (OSError, json.JSONDecodeError):
        return 0


def count_today_records():
    today = date.today().strftime("%Y-%m-%d")
    count = 0
    job_json = _automation_root() / "job" / "output" / f"aniket_projectmate_{today}.json"
    if job_json.exists():
        try:
            with open(job_json, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            count += len(_jobs_from_json_data(data))
        except (OSError, json.JSONDecodeError):
            pass
    posts_xlsx = _automation_root() / "posts" / "output" / f"hiring_posts_{today}.xlsx"
    if posts_xlsx.exists():
        count += 1
    return count


def dashboard_stats():
    return {
        "total_jobs": count_jobs_scraped(),
        "connections_sent": count_connections_sent(),
        "posts_scraped": count_posts_scraped(),
        "today_records": count_today_records(),
        "session": session_status(),
    }


def get_latest_job_output_file():
    """Most recent daily job Excel output (aniket_projectmate_*.xlsx)."""
    output_dir = _automation_root() / "job" / "output"
    if not output_dir.is_dir():
        return None
    candidates = sorted(
        output_dir.glob("aniket_projectmate_*.xlsx"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            stat = path.stat()
            return {
                "name": path.name,
                "path": str(path),
                "rel_path": str(path.relative_to(_automation_root())).replace("\\", "/"),
                "type": "Job Data",
                "date": datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %Y"),
                "mtime": stat.st_mtime,
                "records": _estimate_records(path),
                "size_kb": round(stat.st_size / 1024, 1),
            }
        except OSError:
            continue
    return None


def list_output_files():
    files = []
    root = _automation_root()

    patterns = [
        (root / "job" / "output", "aniket_projectmate_*.xlsx", "Job Data"),
        (root / "job" / "output", "aniket_projectmate_*.json", "Job Data"),
        (root / "job" / "output", "merged_*.xlsx", "Job Data (Merged)"),
        (root / "posts" / "output", "hiring_posts_*.xlsx", "Posts"),
        (root / "connections" / "new_connection", "*.csv", "Connections"),
        (root / "connections" / "new_connection", "*.xlsx", "Connections"),
        (root / "job" / "output", "merged_*.json", "Job Data (Merged)"),
        (root / "job" / "output", "merged_*.csv", "Job Data (Merged)"),
    ]

    for directory, pattern, file_type in patterns:
        if not directory.exists():
            continue
        for path in sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                stat = path.stat()
                record_count = _estimate_records(path)
                files.append(
                    {
                        "name": path.name,
                        "path": str(path),
                        "rel_path": str(path.relative_to(root)).replace("\\", "/"),
                        "type": file_type,
                        "date": datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %Y"),
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %Y %H:%M"),
                        "mtime": stat.st_mtime,
                        "records": record_count,
                        "size_kb": round(stat.st_size / 1024, 1),
                    }
                )
            except OSError:
                continue
    return files


def _estimate_records(path):
    if path.suffix == ".json":
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            jobs = _jobs_from_json_data(data)
            return len(jobs)
        except (OSError, json.JSONDecodeError):
            return 0
    if path.suffix == ".csv":
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return max(0, sum(1 for _ in handle) - 1)
        except OSError:
            return 0
    if path.suffix == ".xlsx":
        try:
            from openpyxl import load_workbook

            wb = load_workbook(path, read_only=True)
            ws = wb.active
            return max(0, ws.max_row - 1)
        except Exception:
            return 0
    return 0


def preview_file(path_str, limit=500):
    path = Path(path_str)
    if not path.exists():
        return {"headers": [], "rows": [], "error": "File not found"}

    if path.suffix == ".json":
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict) and isinstance(data.get("rows"), list):
                rows = data["rows"]
                headers = _order_preview_headers(
                    data.get("columns") or (list(rows[0].keys()) if rows else [])
                )
                body = _rows_from_dicts(headers, rows, limit)
                return attach_preview_rows_zipped({"headers": headers, "rows": body})
            jobs = _jobs_from_json_data(data)
            if not jobs:
                return attach_preview_rows_zipped({"headers": [], "rows": []})
            headers = _order_preview_headers(list(jobs[0].keys()))
            body = _rows_from_dicts(headers, jobs, limit)
            return attach_preview_rows_zipped({"headers": headers, "rows": body})
        except (OSError, json.JSONDecodeError) as exc:
            return {"headers": [], "rows": [], "error": _preview_error(exc, path)}

    if path.suffix == ".csv":
        try:
            with open(path, "r", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                headers = _order_preview_headers(list(reader.fieldnames or []))
                records = list(reader)
            body = _rows_from_dicts(headers, records, limit)
            return attach_preview_rows_zipped({"headers": headers, "rows": body})
        except OSError as exc:
            return {"headers": [], "rows": [], "error": _preview_error(exc, path)}

    if path.suffix == ".xlsx":
        try:
            from openpyxl import load_workbook

            wb = load_workbook(path, read_only=True, data_only=True)
            ws = wb.active
            all_rows = [list(row) for row in ws.iter_rows(values_only=True)]
            wb.close()
            header_idx, raw_headers = _find_xlsx_header_row(all_rows)
            headers = _order_preview_headers([h for h in raw_headers if h])
            records = []
            for row in all_rows[header_idx + 1 : header_idx + 1 + limit]:
                if not row or all(c is None or str(c).strip() == "" for c in row):
                    continue
                record = {}
                for i, header in enumerate(raw_headers):
                    if not header:
                        continue
                    value = row[i] if i < len(row) else ""
                    record[header] = "" if value is None else value
                if any(str(v).strip() for v in record.values()):
                    records.append(record)
            body = _rows_from_dicts(headers, records, limit)
            return attach_preview_rows_zipped({"headers": headers, "rows": body})
        except Exception as exc:
            return {"headers": [], "rows": [], "error": _preview_error(exc, path)}

    return {"headers": [], "rows": [], "error": "Unsupported file type"}


def recent_activity(limit=10):
    events = list(ActivityEvent.objects.all()[:limit])
    if events:
        return events

    fallback = []
    for task in ScraperTask.objects.exclude(status=ScraperTask.STATUS_PENDING)[:limit]:
        fallback.append(
            ActivityEvent(
                event_type=task.task_type,
                title=f"{task.get_task_type_display()} {task.status}",
                detail=json.dumps(task.config)[:200],
                created_at=task.created_at,
            )
        )
    return fallback


def collect_logs(limit=200, task_id=None, search="", sort_by="date", sort_dir="desc"):
    from apps.linkedin.services.filter_utils import sort_logs

    qs = TaskLog.objects.all()
    if task_id:
        qs = qs.filter(task_id=task_id)
    if search:
        qs = qs.filter(message__icontains=search)

    order = "-created_at" if sort_dir != "asc" else "created_at"
    if sort_by == "level":
        order = "-level" if sort_dir != "asc" else "level"
    elif sort_by == "message":
        order = "-message" if sort_dir != "asc" else "message"

    logs = list(qs.order_by(order)[:limit])
    if sort_by not in {"date", "level", "message"}:
        log_dicts = [
            {"level": log.level, "message": log.message, "created_at": log.created_at, "time": log.created_at.strftime("%H:%M:%S")}
            for log in logs
        ]
        return sort_logs(log_dicts, sort_by, sort_dir)
    return logs


def log_automation_files(limit=100):
    logs = []
    log_path = _automation_root() / "connections" / "new_connection" / "connections.log"
    if log_path.exists():
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle.readlines()[-limit:]:
                    logs.append({"level": "info", "message": line.rstrip(), "source": "connections"})
        except OSError:
            pass
    return logs
