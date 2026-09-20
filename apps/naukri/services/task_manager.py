"""Subprocess worker + task manager for Naukri automation."""

import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.naukri.models import NaukriTask, NaukriTaskLog

_active_process = None
_process_lock = threading.Lock()


def get_active_task():
    return (
        NaukriTask.objects.filter(
            status__in=[NaukriTask.STATUS_PENDING, NaukriTask.STATUS_RUNNING]
        )
        .order_by("-created_at")
        .first()
    )


def assert_can_start():
    running = get_active_task()
    if running:
        raise RuntimeError(
            f"{running.get_task_type_display()} is already {running.status}. Stop it first."
        )


def _python_executable():
    return sys.executable


def _worker_env():
    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "config.settings"
    env["PYTHONUNBUFFERED"] = "1"
    base = str(settings.BASE_DIR)
    env["PYTHONPATH"] = base + os.pathsep + env.get("PYTHONPATH", "")
    return env


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


def _stream_output(task_id, process):
    task = NaukriTask.objects.filter(pk=task_id).first()
    if not task:
        return
    try:
        for line in process.stdout:
            message = (line or "").rstrip("\n")
            if not message.strip():
                continue
            level = NaukriTaskLog.LEVEL_INFO
            lower = message.lower()
            if "error" in lower or "***" in message:
                level = NaukriTaskLog.LEVEL_ERROR
            elif "saved" in lower or "done" in lower or "[+]" in message:
                level = NaukriTaskLog.LEVEL_SUCCESS
            NaukriTaskLog.objects.create(task_id=task_id, level=level, message=message)
            task = NaukriTask.objects.filter(pk=task_id).first()
            if task:
                progress = dict(task.progress or {})
                progress["last_message"] = message[:240]
                progress["updated_at"] = timezone.now().isoformat()
                task.progress = progress
                task.save(update_fields=["progress"])
    except Exception:
        pass

    return_code = process.wait()
    task = NaukriTask.objects.filter(pk=task_id).first()
    if not task:
        return
    if task.status == NaukriTask.STATUS_STOPPED:
        return
    if return_code == 0:
        task.mark_finished(NaukriTask.STATUS_COMPLETED)
        NaukriTaskLog.objects.create(
            task=task, level=NaukriTaskLog.LEVEL_SUCCESS, message="Task finished successfully."
        )
    else:
        task.mark_finished(NaukriTask.STATUS_FAILED, f"Process exited with code {return_code}")
        NaukriTaskLog.objects.create(
            task=task,
            level=NaukriTaskLog.LEVEL_ERROR,
            message=f"Process exited with code {return_code}",
        )


def start_task(task_type, config=None):
    global _active_process
    assert_can_start()

    task = NaukriTask.objects.create(
        task_type=task_type,
        status=NaukriTask.STATUS_PENDING,
        config=dict(config or {}),
        progress={"percent": 0},
    )

    cmd = [_python_executable(), "-m", "apps.naukri.services.run_worker", str(task.id)]
    popen_kwargs = {
        "cwd": str(settings.BASE_DIR),
        "env": _worker_env(),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "bufsize": 1,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    process = subprocess.Popen(cmd, **popen_kwargs)
    with _process_lock:
        _active_process = process
    task.mark_running(process.pid)
    NaukriTaskLog.objects.create(
        task=task,
        level=NaukriTaskLog.LEVEL_INFO,
        message=f"Background process started (PID {process.pid})",
    )
    threading.Thread(target=_stream_output, args=(task.id, process), daemon=True).start()
    return task


def stop_task(task_id=None):
    global _active_process
    task = NaukriTask.objects.filter(pk=task_id).first() if task_id else get_active_task()
    if not task:
        return {"ok": False, "message": "No active Naukri task"}

    data_dir = Path(settings.NAUKRI_DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / f"stop_task_{task.id}").write_text("1", encoding="utf-8")

    pid = task.pid
    killed = _kill_process_tree(pid, force=True) if pid else False
    with _process_lock:
        if _active_process and _active_process.pid == pid:
            _active_process = None

    task.mark_finished(NaukriTask.STATUS_STOPPED, "Stopped by user")
    NaukriTaskLog.objects.create(
        task=task, level=NaukriTaskLog.LEVEL_WARNING, message="Stopped by user"
    )
    return {"ok": True, "message": "Stopped", "killed": killed}


def task_status_payload(task=None):
    task = task or get_active_task()
    if not task:
        return {"ok": True, "active": False, "task": None, "logs": []}
    logs = list(
        NaukriTaskLog.objects.filter(task=task)
        .order_by("-id")[:40]
        .values("level", "message", "created_at")
    )
    logs.reverse()
    for item in logs:
        item["created_at"] = item["created_at"].isoformat()
    return {
        "ok": True,
        "active": task.is_active,
        "task": {
            "id": task.id,
            "task_type": task.task_type,
            "task_type_label": task.get_task_type_display(),
            "status": task.status,
            "progress": task.progress or {},
            "error_message": task.error_message,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        },
        "logs": logs,
    }


def list_output_files():
    root = Path(settings.NAUKRI_AUTOMATION_ROOT) / "output"
    if not root.exists():
        return []
    files = []
    for path in sorted(root.glob("*.*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.suffix.lower() not in {".csv", ".xlsx"}:
            continue
        files.append(
            {
                "name": path.name,
                "path": str(path),
                "size": path.stat().st_size,
                "modified": path.stat().st_mtime,
            }
        )
    return files


def session_exists():
    path = Path(settings.NAUKRI_AUTOMATION_ROOT) / "storage_state.json"
    return path.exists() and path.stat().st_size > 20
