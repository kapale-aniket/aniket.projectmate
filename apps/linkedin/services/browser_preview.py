"""
Live browser preview for in-app scraping view (headless Playwright + screenshot stream).
State is file-based so the worker subprocess and Django process can share it.

Screenshots MUST run on the Playwright owner thread (sync API uses greenlets).
Do not capture from a background thread.
"""

import json
import os
import threading
import time
from pathlib import Path

from django.conf import settings

PREVIEW_DIR = Path(settings.BASE_DIR) / "data" / "browser_preview"
STATE_FILE = PREVIEW_DIR / "state.json"

_registered_page = None
_registered_task_id = None
_last_capture_at = 0.0
_capture_min_interval = 1.0
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


def screenshot_path(task_id):
    return PREVIEW_DIR / f"task_{task_id}.jpg"


def unregister_page():
    """Clear page reference when the browser closes."""
    global _registered_page, _registered_task_id
    with _page_lock:
        _registered_page = None
        _registered_task_id = None


def register_page(page, task_id):
    """Store the active Playwright page — capture runs on the scraper thread only."""
    global _registered_page, _registered_task_id, _last_capture_at
    with _page_lock:
        _registered_page = page
        _registered_task_id = task_id
    _last_capture_at = 0.0

    # Hook waits so preview frames refresh without a background thread.
    if page is not None and not getattr(page, "_terra_preview_patched", False):
        original_wait = page.wait_for_timeout

        def wait_for_timeout(timeout):
            maybe_capture_screenshot(page, task_id)
            return original_wait(timeout)

        page.wait_for_timeout = wait_for_timeout
        page._terra_preview_patched = True

    maybe_capture_screenshot(page, task_id)


def maybe_capture_screenshot(page=None, task_id=None):
    """Take a preview frame if Show is enabled (call from the Playwright thread only)."""
    global _last_capture_at

    state = get_state()
    if not state.get("enabled"):
        return

    tid = task_id or state.get("task_id")
    if not tid:
        tid = os.environ.get("TERRA_TASK_ID")
    if not tid:
        return

    if state.get("task_id") is not None and int(state["task_id"]) != int(tid):
        return

    target = page
    if target is None:
        with _page_lock:
            target = _registered_page
            if not tid:
                tid = _registered_task_id
    if target is None:
        return

    now = time.time()
    if now - _last_capture_at < _capture_min_interval:
        return
    _last_capture_at = now

    try:
        _ensure_dir()
        target.screenshot(
            path=str(screenshot_path(int(tid))),
            type="jpeg",
            quality=72,
            full_page=False,
            timeout=5000,
        )
    except Exception:
        pass


def clear_preview(task_id):
    path = screenshot_path(task_id)
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
