"""
Live browser preview for in-app scraping view (headless Playwright + screenshot stream).
State is file-based so the worker subprocess and Django process can share it.
"""

import json
import threading
import time
from pathlib import Path

from django.conf import settings

PREVIEW_DIR = Path(settings.BASE_DIR) / "data" / "browser_preview"
STATE_FILE = PREVIEW_DIR / "state.json"

_capture_thread = None
_capture_stop = threading.Event()
_registered_page = None
_registered_task_id = None
_page_lock = threading.Lock()


def _ensure_dir():
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)


def get_state():
    _ensure_dir()
    if not STATE_FILE.exists():
        return {"enabled": False, "task_id": None}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"enabled": False, "task_id": None}


def set_preview_enabled(enabled, task_id=None):
    _ensure_dir()
    STATE_FILE.write_text(
        json.dumps({"enabled": bool(enabled), "task_id": task_id}),
        encoding="utf-8",
    )
    if not enabled:
        _capture_stop.set()


def screenshot_path(task_id):
    return PREVIEW_DIR / f"task_{task_id}.jpg"


def register_page(page, task_id):
    global _registered_page, _registered_task_id, _capture_thread

    with _page_lock:
        _registered_page = page
        _registered_task_id = task_id

    _start_capture_thread(task_id)


def _start_capture_thread(task_id):
    global _capture_thread

    if _capture_thread and _capture_thread.is_alive():
        return

    _capture_stop.clear()

    def loop():
        while not _capture_stop.is_set():
            state = get_state()
            if not state.get("enabled") or state.get("task_id") != task_id:
                time.sleep(0.4)
                continue

            with _page_lock:
                page = _registered_page

            if page is None:
                time.sleep(0.4)
                continue

            try:
                _ensure_dir()
                page.screenshot(
                    path=str(screenshot_path(task_id)),
                    type="jpeg",
                    quality=72,
                    full_page=False,
                )
            except Exception:
                pass

            time.sleep(1.0)

    _capture_thread = threading.Thread(target=loop, daemon=True, name="browser-preview")
    _capture_thread.start()


def clear_preview(task_id):
    path = screenshot_path(task_id)
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
