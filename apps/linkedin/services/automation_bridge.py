"""
Hooks automation stdout and browser launch to the Django task system.
"""

import builtins
import contextlib
import functools
import os
import sys


def _configure_stdout_encoding():
    """Avoid UnicodeEncodeError on Windows cp1252 consoles."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _safe_write_print(original_print, *args, **kwargs):
    """Never let console I/O crash the scraper (common on Windows pipes)."""
    kwargs = dict(kwargs)
    # Drop flush on first attempt if it tends to raise Errno 22 on broken pipes.
    flush = bool(kwargs.pop("flush", False))

    try:
        original_print(*args, flush=flush, **kwargs)
        return
    except (UnicodeEncodeError, OSError, ValueError, BrokenPipeError):
        pass
    except RecursionError:
        raise

    file = kwargs.get("file", sys.stdout)
    text = " ".join(str(arg) for arg in args)
    end = kwargs.get("end", "\n")

    # Retry without flush / with ASCII-safe text.
    try:
        encoding = getattr(file, "encoding", None) or "utf-8"
        safe = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        original_print(safe, end=end, file=file, flush=False)
        return
    except Exception:
        pass

    try:
        buffer = getattr(file, "buffer", None)
        if buffer is not None:
            buffer.write((text + end).encode("utf-8", errors="replace"))
            return
    except Exception:
        pass

    # Last resort: write to stderr, still never raise.
    try:
        sys.__stderr__.write(text + end)
    except Exception:
        pass


def install_automation_hooks(task):
    _configure_stdout_encoding()
    os.environ["TERRA_TASK_ID"] = str(task.id)
    config = task.config or {}

    # Scrapers run headless; live view is shown in-app via Show Scraping (screenshot stream).
    if task.task_type != "session":
        os.environ["TERRA_HEADLESS"] = "1"
        config = {**config, "headless": True}
    elif config.get("headless") is not None:
        os.environ["TERRA_HEADLESS"] = "1" if config.get("headless") else "0"

    _patch_print(task.id)
    _patch_browser_launch(task, config.get("headless"))


def _patch_print(task_id):
    if getattr(builtins.print, "__terra_tee_print__", False):
        return

    original_print = builtins.print

    @functools.wraps(original_print)
    def tee_print(*args, **kwargs):
        try:
            _safe_write_print(original_print, *args, **kwargs)
        except Exception:
            pass
        try:
            message = " ".join(str(arg) for arg in args)
            if not message.strip():
                return
            from apps.linkedin.models import ScraperTask
            from apps.linkedin.services.progress_tracker import update_task_progress

            task = ScraperTask.objects.filter(pk=task_id).first()
            if task:
                update_task_progress(task, message)
        except Exception:
            pass

    tee_print.__terra_tee_print__ = True
    builtins.print = tee_print


def _patch_browser_launch(task, headless=None):
    try:
        import common.browser as browser_module
    except ImportError:
        return

    original_launch = browser_module.launch_browser
    task_id = task.id
    is_scraper = task.task_type != "session"

    @contextlib.contextmanager
    def patched_launch(*args, **kwargs):
        env_headless = os.environ.get("TERRA_HEADLESS")
        if is_scraper:
            kwargs["headless"] = True
        elif headless is not None:
            kwargs["headless"] = bool(headless)
        elif env_headless is not None:
            kwargs["headless"] = env_headless == "1"

        with original_launch(*args, **kwargs) as result:
            if is_scraper and len(result) >= 3:
                from apps.linkedin.services.browser_preview import register_page, unregister_page

                register_page(result[2], task_id)
            try:
                yield result
            finally:
                if is_scraper:
                    unregister_page()

    browser_module.launch_browser = patched_launch

    for module_name in list(sys.modules):
        if module_name.endswith(".browser") and hasattr(sys.modules[module_name], "launch_browser"):
            sys.modules[module_name].launch_browser = patched_launch
