import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.linkedin.models import ActivityEvent, ScraperTask, TaskLog
from apps.linkedin.services.config_service import load_settings, save_settings, sync_to_automation_configs
from apps.linkedin.services.progress_tracker import (
    build_job_search_checklist,
    get_live_progress,
    update_task_progress,
)


_active_process = None
_process_lock = threading.Lock()


def get_active_task():
    return (
        ScraperTask.objects.filter(
            status__in=[
                ScraperTask.STATUS_PENDING,
                ScraperTask.STATUS_RUNNING,
                ScraperTask.STATUS_PAUSED,
            ]
        )
        .order_by("-created_at")
        .first()
    )


def get_running_task():
    """Task that is actively executing (pending or running)."""
    return (
        ScraperTask.objects.filter(
            status__in=[ScraperTask.STATUS_PENDING, ScraperTask.STATUS_RUNNING]
        )
        .order_by("-created_at")
        .first()
    )


def busy_task_message(task):
    label = task.get_task_type_display()
    if task.status == ScraperTask.STATUS_PAUSED:
        return f"{label} scraping is paused. Wait or stop it to start this scraper."
    return f"{label} scraping is running. Wait or stop it to start this scraper."


def task_page_url(task_type):
    routes = {
        ScraperTask.TASK_JOB: "/admin/linkedin/jobs/",
        ScraperTask.TASK_PERFECT_MATCH: "/admin/linkedin/perfect-match/",
        ScraperTask.TASK_CONNECTION: "/admin/linkedin/connections/",
        ScraperTask.TASK_POSTS: "/admin/linkedin/posts/",
        ScraperTask.TASK_SESSION: "/admin/linkedin/session/",
    }
    return routes.get(task_type, "/admin/linkedin/")


def assert_can_start_scraper(resume=False):
    running = get_running_task()
    if running:
        raise RuntimeError(busy_task_message(running))

    if resume:
        return

    active = get_active_task()
    if active and active.status == ScraperTask.STATUS_PAUSED:
        raise RuntimeError(busy_task_message(active))


def _python_executable():
    return sys.executable


def _worker_env():
    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "config.settings"
    env["PYTHONUNBUFFERED"] = "1"
    base = str(settings.BASE_DIR)
    env["PYTHONPATH"] = base + os.pathsep + env.get("PYTHONPATH", "")
    from apps.linkedin.services.job_output_service import worker_env_extras

    env.update(worker_env_extras())
    return env


def _worker_command(task_id):
    return [_python_executable(), "-m", "apps.linkedin.services.run_worker", str(task_id)]


def _kill_process_tree(pid, force=False):
    if not pid:
        return False
    try:
        if os.name == "nt":
            args = ["taskkill", "/T", "/PID", str(pid)]
            if force:
                args.insert(1, "/F")
            result = subprocess.run(args, capture_output=True, text=True)
            return result.returncode == 0
        sig = signal.SIGKILL if force else signal.SIGTERM
        try:
            os.killpg(os.getpgid(pid), sig)
        except (OSError, ProcessLookupError, AttributeError):
            os.kill(pid, sig)
        return True
    except (OSError, ProcessLookupError):
        return False


def _request_graceful_stop(pid):
    """Stop is coordinated via the stop flag file; avoid signals that crash Playwright."""
    return bool(pid)


def _wait_for_process(process, pid, timeout_seconds=25):
    if process is not None:
        try:
            return process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            return None
    if not pid:
        return None
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return 0
        time.sleep(0.25)
    return None


def _finalize_task_output(task):
    if task.task_type not in (ScraperTask.TASK_JOB, ScraperTask.TASK_PERFECT_MATCH):
        return
    try:
        from apps.linkedin.services.job_output_service import finalize_job_output

        scrape_mode = "perfect_match" if task.task_type == ScraperTask.TASK_PERFECT_MATCH else "job"
        path = finalize_job_output(scrape_mode=scrape_mode)
        if path:
            TaskLog.objects.create(
                task=task,
                level=TaskLog.LEVEL_INFO,
                message=f"Output file ready: {os.path.basename(path)}",
            )
    except Exception as exc:
        TaskLog.objects.create(
            task=task,
            level=TaskLog.LEVEL_WARNING,
            message=f"Could not refresh output file: {exc}",
        )


def _stream_output(task, process):
    global _active_process
    try:
        for raw_line in iter(process.stdout.readline, ""):
            if not raw_line:
                break
            line = raw_line.rstrip()
            if not line:
                continue
            level = TaskLog.LEVEL_INFO
            lower = line.lower()
            if "error" in lower or "***" in line:
                level = TaskLog.LEVEL_ERROR
            elif "success" in lower or "completed" in lower or "saved" in lower:
                level = TaskLog.LEVEL_SUCCESS
            TaskLog.objects.create(task=task, level=level, message=line)
            task.refresh_from_db()
            update_task_progress(task, line)
    finally:
        return_code = process.wait()
        with _process_lock:
            if _active_process is process:
                _active_process = None

        task.refresh_from_db()
        if task.status in {
            ScraperTask.STATUS_STOPPED,
            ScraperTask.STATUS_COMPLETED,
            ScraperTask.STATUS_FAILED,
        }:
            _finalize_task_output(task)
        elif return_code == 0:
            progress = dict(task.progress or {})
            progress["percent"] = 100
            task.progress = progress
            task.mark_finished(ScraperTask.STATUS_COMPLETED)
            TaskLog.objects.create(
                task=task, level=TaskLog.LEVEL_SUCCESS, message="Task finished successfully."
            )
            _finalize_task_output(task)
        else:
            task.mark_finished(ScraperTask.STATUS_FAILED, f"Process exited with code {return_code}")
            TaskLog.objects.create(
                task=task,
                level=TaskLog.LEVEL_ERROR,
                message=f"Process exited with code {return_code}",
            )
            _finalize_task_output(task)


def start_task(task_type, config=None, run_in_background=True, resume=False):
    global _active_process

    assert_can_start_scraper(resume=resume)

    sync_to_automation_configs(load_settings())

    if task_type in (ScraperTask.TASK_JOB, ScraperTask.TASK_PERFECT_MATCH):
        try:
            from apps.linkedin.services.automation_path import ensure_automation_path

            ensure_automation_path()
            from job.master_store import purge_old_files

            purge_old_files()
        except Exception:
            pass

    merged_config = dict(config or {})
    if resume:
        merged_config["resume"] = True
    if task_type == ScraperTask.TASK_PERFECT_MATCH:
        merged_config["scrape_mode"] = "perfect_match"
        # Ensure automation config.py matches Perfect Match skills (not Jobs keywords).
        skills = merged_config.get("skills") or []
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.splitlines() if s.strip()]
        locations = merged_config.get("locations") or []
        if isinstance(locations, str):
            locations = [s.strip() for s in locations.splitlines() if s.strip()]
        search_query = " ".join(str(s).strip() for s in skills if str(s).strip())
        if search_query:
            merged_config["keywords"] = [search_query]
            try:
                from apps.linkedin.services.automation_path import ensure_automation_path

                ensure_automation_path()
                import job.config as job_cfg

                job_cfg.JOB_KEYWORDS = [search_query]
                job_cfg.LOCATIONS = list(locations) if locations else list(getattr(job_cfg, "LOCATIONS", []) or [])
                job_cfg.SCRAPE_MODE = "perfect_match"
                job_cfg.PERFECT_MATCH_SKILLS = list(skills)
                job_cfg.PERFECT_MATCH_EXPERIENCE = str(merged_config.get("experience") or "")
                try:
                    job_cfg.PERFECT_MATCH_MIN_SKILLS = max(
                        1, int(merged_config.get("min_skills_match") or 1)
                    )
                except (TypeError, ValueError):
                    job_cfg.PERFECT_MATCH_MIN_SKILLS = 1
                job_cfg.SHEET_TITLE = "skill match job"
            except Exception:
                pass

    task = ScraperTask.objects.create(
        task_type=task_type,
        status=ScraperTask.STATUS_PENDING,
        config=merged_config,
        run_in_background=run_in_background,
        progress={"percent": 0},
    )

    ActivityEvent.objects.create(
        event_type=task_type,
        title=f"{task.get_task_type_display()} started",
        detail=json.dumps(merged_config)[:500],
    )

    cwd = str(settings.BASE_DIR)
    popen_kwargs = {
        "cwd": cwd,
        "env": _worker_env(),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "bufsize": 1,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    process = subprocess.Popen(_worker_command(task.id), **popen_kwargs)

    with _process_lock:
        _active_process = process

    task.mark_running(process.pid)
    TaskLog.objects.create(
        task=task,
        level=TaskLog.LEVEL_INFO,
        message=f"Background process started (PID {process.pid})",
    )

    thread = threading.Thread(target=_stream_output, args=(task, process), daemon=True)
    thread.start()
    return task


def stop_task(task_id=None):
    global _active_process

    task = ScraperTask.objects.filter(pk=task_id).first() if task_id else get_active_task()
    if not task:
        return {"ok": False, "message": "No active task"}

    from apps.linkedin.services.job_output_service import clear_task_stop_flag, request_task_stop

    request_task_stop(task.id)

    task.refresh_from_db()
    if task.status not in {
        ScraperTask.STATUS_STOPPED,
        ScraperTask.STATUS_COMPLETED,
        ScraperTask.STATUS_FAILED,
    }:
        task.mark_finished(ScraperTask.STATUS_STOPPED, "Stopped by user")

    process = None
    pid = task.pid
    with _process_lock:
        if _active_process and _active_process.poll() is None:
            process = _active_process
            pid = _active_process.pid

    if pid:
        _request_graceful_stop(pid)
        exit_code = _wait_for_process(process, pid, timeout_seconds=25)
        if exit_code is None:
            with _process_lock:
                if _active_process and _active_process.poll() is None:
                    _kill_process_tree(_active_process.pid, force=True)
                    _active_process = None
                elif pid:
                    _kill_process_tree(pid, force=True)

    clear_task_stop_flag(task.id)

    task.refresh_from_db()
    progress = dict(task.progress or {})
    task.progress = progress
    task.pid = None
    task.save(update_fields=["progress", "pid"])
    try:
        from apps.linkedin.services.browser_preview import set_preview_enabled

        set_preview_enabled(False, task.id)
    except Exception:
        pass
    TaskLog.objects.create(task=task, level=TaskLog.LEVEL_WARNING, message="Task stopped by user")
    output_name = ""
    try:
        from apps.linkedin.services.job_output_service import finalize_job_output

        output_path = finalize_job_output()
        if output_path:
            output_name = os.path.basename(output_path)
            TaskLog.objects.create(
                task=task,
                level=TaskLog.LEVEL_INFO,
                message=f"Output file ready: {output_name}",
            )
    except Exception as exc:
        TaskLog.objects.create(
            task=task,
            level=TaskLog.LEVEL_WARNING,
            message=f"Could not refresh output file: {exc}",
        )
    message = "Task stopped"
    if output_name:
        message = f'Task stopped. Output saved as "{output_name}".'
    ActivityEvent.objects.create(
        event_type=task.task_type,
        title=f"{task.get_task_type_display()} stopped",
        detail="Stopped from Aniket.Project Mate UI",
    )
    return {"ok": True, "message": message, "task_id": task.id}


def pause_task(task_id=None):
    task = ScraperTask.objects.filter(pk=task_id).first() if task_id else get_active_task()
    if not task or task.status != ScraperTask.STATUS_RUNNING:
        return {"ok": False, "message": "No running task to pause"}
    stop_task(task.id)
    task.refresh_from_db()
    task.status = ScraperTask.STATUS_PAUSED
    task.pid = None
    task.save(update_fields=["status", "pid"])
    TaskLog.objects.create(task=task, level=TaskLog.LEVEL_WARNING, message="Task paused (checkpoint saved)")
    return {"ok": True, "message": "Task paused", "task_id": task.id}


def resume_task(task_id=None, config=None):
    assert_can_start_scraper(resume=True)

    paused = ScraperTask.objects.filter(status=ScraperTask.STATUS_PAUSED).order_by("-created_at").first()
    task = ScraperTask.objects.filter(pk=task_id).first() if task_id else paused

    if not task or task.status != ScraperTask.STATUS_PAUSED:
        raise RuntimeError("No paused task to resume.")

    merged = {**(task.config or {}), **(config or {}), "resume": True}
    return start_task(task.task_type, config=merged, resume=True)


def task_status_payload(task):
    if not task:
        return {"active": False, "status": "idle", "can_start": True, "task_url": "/"}

    live = get_live_progress(task)
    logs = list(task.logs.order_by("-created_at")[:30])

    elapsed = "00:00:00"
    if task.started_at:
        delta = (task.finished_at or timezone.now()) - task.started_at
        total = int(delta.total_seconds())
        elapsed = f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"

    config = task.config or {}
    progress_data = dict(task.progress or {})
    is_busy = task.status in {
        ScraperTask.STATUS_PENDING,
        ScraperTask.STATUS_RUNNING,
        ScraperTask.STATUS_PAUSED,
    }

    return {
        "active": task.is_active,
        "can_start": not is_busy,
        "busy_message": busy_task_message(task) if is_busy else "",
        "task_url": task_page_url(task.task_type),
        "id": task.id,
        "task_type": task.task_type,
        "task_type_label": task.get_task_type_display(),
        "status": task.status,
        "elapsed": elapsed,
        "keyword": live.get("keyword") or _first(config.get("keywords")),
        "location": live.get("location") or _first(config.get("locations")),
        "page": live.get("page", "-"),
        "jobs_found": live.get("jobs_found", 0),
        "connections_sent": live.get("connections_sent", 0),
        "posts_checked": live.get("posts_checked", 0),
        "progress_pct": live.get("percent", 0),
        "message": live.get("message", ""),
        "output_file": progress_data.get("output_file", ""),
        "completion_message": progress_data.get("completion_message", ""),
        "search_checklist": build_job_search_checklist(task),
        "logs": [
            {
                "level": log.level,
                "message": log.message,
                "time": log.created_at.strftime("%H:%M:%S"),
            }
            for log in reversed(logs)
        ],
        "error": task.error_message,
    }


def _first(value):
    if isinstance(value, list):
        return value[0] if value else ""
    return value or ""


def ensure_settings_initialized():
    save_settings(load_settings())
