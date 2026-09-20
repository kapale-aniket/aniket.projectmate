"""Merge multiple output files by aligning rows on shared column headers."""

import csv
import json
from datetime import datetime
from pathlib import Path

from django.conf import settings

from apps.linkedin.services.automation_path import ensure_automation_path
from apps.linkedin.services.stats import filter_preview_columns


JOB_JSON_TO_EXCEL = {
    "job_role": "Job Role",
    "company_name": "Company Name",
    "company_size": "Company Size",
    "freshers_eligible": "Freshers Eligible",
    "experience_required": "Experience Required",
    "skills_required": "Skills Required",
    "location": "Location",
    "package_lpa": "Package (LPA)",
    "posted_text": "Posted",
    "easy_apply": "Easy Apply",
    "apply_link": "Apply Link",
}

EXCEL_TO_JOB_JSON = {v: k for k, v in JOB_JSON_TO_EXCEL.items()}

DEDUPE_CANDIDATES = (
    "apply_link",
    "Apply Link",
    "job_id",
    "Job ID",
    "profile_url",
    "Profile URL",
    "url",
    "URL",
)


def _automation_root():
    return Path(settings.LINKEDIN_AUTOMATION_ROOT)


def _validate_paths(paths):
    allowed_roots = [
        Path(settings.LINKEDIN_AUTOMATION_ROOT).resolve(),
        Path(settings.NAUKRI_AUTOMATION_ROOT).resolve(),
    ]
    validated = []
    for path_str in paths:
        path = Path(path_str).resolve()
        if not any(str(path).startswith(str(root)) for root in allowed_roots) or not path.exists():
            raise ValueError(f"Invalid or missing file: {path.name}")
        if path.suffix.lower() not in {".json", ".csv", ".xlsx"}:
            raise ValueError(f"Unsupported file type: {path.name}")
        validated.append(path)
    if len(validated) < 2:
        raise ValueError("Select at least two files to merge.")
    return validated


def _normalize_key(key):
    ensure_automation_path()
    from common.tabular_io import normalize_header_key

    return normalize_header_key(key)


def read_tabular_file(path):
    ensure_automation_path()
    from common.tabular_io import read_tabular_file as _read_tabular_file

    return _read_tabular_file(path)


def _union_headers(header_lists):
    merged = []
    seen = set()
    for headers in header_lists:
        for header in headers:
            key = _normalize_key(header)
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(key)
    return merged


def _row_to_values(row, headers):
    return [row.get(header, "") for header in headers]


def _detect_dedupe_column(headers):
    lower_map = {_normalize_key(h).lower(): h for h in headers}
    for candidate in DEDUPE_CANDIDATES:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    return None


def merge_files(paths, dedupe=True, dedupe_column=None, output_format="xlsx"):
    validated = _validate_paths(paths)
    all_headers = []
    all_rows = []

    for path in validated:
        headers, rows = read_tabular_file(path)
        all_headers.append(headers)
        for row in rows:
            normalized = {_normalize_key(k): v for k, v in row.items()}
            normalized["_source_file"] = path.name
            all_rows.append(normalized)

    unified_headers = _union_headers(all_headers)
    if "_source_file" not in unified_headers:
        unified_headers.append("_source_file")

    dedupe_col = dedupe_column or _detect_dedupe_column(unified_headers)
    seen = set()
    merged_rows = []

    for row in all_rows:
        if dedupe and dedupe_col:
            dedupe_val = str(row.get(dedupe_col, "")).strip().lower()
            if dedupe_val and dedupe_val in seen:
                continue
            if dedupe_val:
                seen.add(dedupe_val)

        merged_rows.append({header: row.get(header, "") for header in unified_headers})

    output_dir = validated[0].parent
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    ext = output_format.lower().lstrip(".")
    if ext not in {"xlsx", "json", "csv"}:
        ext = "xlsx"
    output_name = f"merged_{stamp}.{ext}"
    output_path = output_dir / output_name

    if ext == "json":
        _write_json(output_path, unified_headers, merged_rows)
    elif ext == "csv":
        _write_csv(output_path, unified_headers, merged_rows)
    else:
        _write_xlsx(output_path, unified_headers, merged_rows)

    return {
        "path": str(output_path),
        "name": output_name,
        "records": len(merged_rows),
        "columns": unified_headers,
        "dedupe_column": dedupe_col,
        "source_files": [p.name for p in validated],
    }


def _write_json(path, headers, rows):
    payload = {
        "merged_at": datetime.now().isoformat(timespec="seconds"),
        "columns": headers,
        "rows": rows,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _write_csv(path, headers, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _write_xlsx(path, headers, rows):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    from apps.linkedin.services.excel_io import atomic_workbook_save

    wb = Workbook()
    ws = wb.active
    ws.title = "Merged Data"
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append(_row_to_values(row, headers))
    atomic_workbook_save(wb, path)


def preview_merge(paths, limit=100):
    validated = _validate_paths(paths)
    all_headers = []
    all_rows = []

    for path in validated:
        headers, rows = read_tabular_file(path)
        all_headers.append(headers)
        for row in rows:
            normalized = {_normalize_key(k): v for k, v in row.items()}
            normalized["_source_file"] = path.name
            all_rows.append(normalized)

    unified_headers = filter_preview_columns(_union_headers(all_headers))
    if "_source_file" not in unified_headers:
        unified_headers.append("_source_file")

    preview_rows = []
    for row in all_rows[:limit]:
        preview_rows.append(
            [str(row.get(header, ""))[:120] for header in unified_headers]
        )

    return {
        "headers": unified_headers,
        "rows": preview_rows,
        "total_rows": len(all_rows),
        "source_files": [p.name for p in validated],
    }
