import os
from datetime import date

from common.json_store import load_json, save_json

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
STATE_FILE = os.path.join(OUTPUT_DIR, "posts_state.json")


def purge_old_files(retention_days=4, day=None):
    """Remove posts Excel files older than `retention_days` days.

    Deletes files named like `hiring_posts_YYYY-MM-DD.xlsx` and numeric-suffixed
    variants (e.g. _1, _2).
    """
    from datetime import timedelta
    import re

    today = day or date.today()
    cutoff = today - timedelta(days=retention_days)

    pattern = re.compile(r"^hiring_posts_(\d{4}-\d{2}-\d{2})(?:_\d+)?\.xlsx$")
    for path in [
        os.path.join(OUTPUT_DIR, p) for p in os.listdir(OUTPUT_DIR) if p.endswith(".xlsx")
    ]:
        basename = os.path.basename(path)
        m = pattern.match(basename)
        if not m:
            continue
        try:
            file_day = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except Exception:
            continue
        if file_day <= cutoff:
            try:
                os.remove(path)
            except OSError:
                pass


def _today_str():
    return date.today().strftime("%Y-%m-%d")


def daily_excel_path(day=None):
    day_str = day.strftime("%Y-%m-%d") if day else _today_str()
    base = os.path.join(OUTPUT_DIR, f"hiring_posts_{day_str}.xlsx")
    if not os.path.exists(base):
        return base

    index = 1
    while True:
        candidate = os.path.join(OUTPUT_DIR, f"hiring_posts_{day_str}_{index}.xlsx")
        if not os.path.exists(candidate):
            return candidate
        index += 1


def empty_state():
    return {
        "last_checked_post_id": "",
        "checked_post_ids": [],
        "hiring_posts": [],
    }


def load_state():
    data = load_json(STATE_FILE, default=empty_state)
    checked = data.get("checked_post_ids")
    hiring = data.get("hiring_posts")
    return {
        "last_checked_post_id": data.get("last_checked_post_id", "") or "",
        "checked_post_ids": checked if isinstance(checked, list) else [],
        "hiring_posts": hiring if isinstance(hiring, list) else [],
    }


def save_state(state):
    save_json(STATE_FILE, state)


def checked_post_id_set(state):
    return set(state.get("checked_post_ids", []))
