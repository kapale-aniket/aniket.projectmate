"""
Subprocess worker for Naukri tasks.
Invoked as: python -m apps.naukri.services.run_worker <task_id>
"""

import os
import sys
import traceback


def _setup_path():
    from django.conf import settings

    root = str(settings.NAUKRI_AUTOMATION_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _log(task, level, message):
    from apps.naukri.models import NaukriTaskLog

    NaukriTaskLog.objects.create(task=task, level=level, message=message)
    print(message, flush=True)


def _run_apply(task):
    from run import run

    run(config=task.config or {})


def _run_session(task):
    from save_session import main as save_session_main

    save_session_main()


def run_task(task_id):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    _setup_path()

    from apps.naukri.models import NaukriTask, NaukriTaskLog

    task = NaukriTask.objects.get(pk=task_id)
    os.environ["TERRA_TASK_ID"] = str(task.id)
    os.environ["NAUKRI_TASK_ID"] = str(task.id)
    _log(task, NaukriTaskLog.LEVEL_INFO, f"Starting {task.get_task_type_display()}...")

    handlers = {
        NaukriTask.TASK_APPLY: _run_apply,
        NaukriTask.TASK_SESSION: _run_session,
    }
    handler = handlers.get(task.task_type)
    if not handler:
        raise RuntimeError(f"Unknown Naukri task type: {task.task_type}")

    try:
        # Respect UI headless flag (Show starts with headless=False → visible Naukri window)
        if task.task_type == NaukriTask.TASK_APPLY:
            cfg = dict(task.config or {})
            cfg.setdefault("headless", False)
            task.config = cfg
            task.save(update_fields=["config"])
            mode = "headless" if cfg.get("headless") else "visible window"
            _log(task, NaukriTaskLog.LEVEL_INFO, f"Browser mode: {mode}")
        handler(task)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if code != 0:
            raise RuntimeError(f"Process exited with code {code}") from exc
    except Exception:
        tb = traceback.format_exc()
        _log(task, NaukriTaskLog.LEVEL_ERROR, tb)
        raise


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m apps.naukri.services.run_worker <task_id>")
        sys.exit(1)
    run_task(int(sys.argv[1]))


if __name__ == "__main__":
    main()
