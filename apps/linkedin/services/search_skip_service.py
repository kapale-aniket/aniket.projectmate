"""Runtime skip list for active job scrapes (read by automation worker)."""

import json
from pathlib import Path

from django.conf import settings


def skip_file_path(task_id):
    return Path(settings.LINKEDIN_DATA_DIR) / f"skip_searches_task_{task_id}.json"


def write_skip_searches(task_id, skip_searches):
    settings.LINKEDIN_DATA_DIR.mkdir(parents=True, exist_ok=True)
    skip_file_path(task_id).write_text(
        json.dumps(list(skip_searches or []), ensure_ascii=False),
        encoding="utf-8",
    )


def read_skip_searches(task_id):
    path = skip_file_path(task_id)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data) if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError, TypeError):
        return []


def clear_skip_searches(task_id):
    try:
        skip_file_path(task_id).unlink()
    except OSError:
        pass
