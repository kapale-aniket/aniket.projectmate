"""
Hooks automation stdout and browser launch to the Django task system.
"""

import builtins
import contextlib
import functools
import os
import sys


def install_automation_hooks(task):
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
    original_print = builtins.print

    @functools.wraps(original_print)
    def tee_print(*args, **kwargs):
        original_print(*args, **kwargs)
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
                from apps.linkedin.services.browser_preview import register_page

                register_page(result[2], task_id)
            yield result

    browser_module.launch_browser = patched_launch

    for module_name in list(sys.modules):
        if module_name.endswith(".browser") and hasattr(sys.modules[module_name], "launch_browser"):
            sys.modules[module_name].launch_browser = patched_launch
