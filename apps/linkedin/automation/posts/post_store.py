import os
from datetime import date

from common.json_store import load_json, save_json

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
STATE_FILE = os.path.join(OUTPUT_DIR, "posts_state.json")


def _today_str():
    return date.today().strftime("%Y-%m-%d")


def daily_excel_path(day=None):
    day_str = day.strftime("%Y-%m-%d") if day else _today_str()
    return os.path.join(OUTPUT_DIR, f"hiring_posts_{day_str}.xlsx")


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
